"""Command line interface for Vibe Guard (SPEC-ENG-4, SPEC-REP-1, Section 4.3)."""

import argparse
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from vibe_guard.audit.models import ScanAuditRecord
from vibe_guard.audit.recorder import AuditRecorder
from vibe_guard.engine.scanner import ScanEngine
from vibe_guard.ingest.workspace import EphemeralWorkspace, IngestionError
from vibe_guard.remediation.generator import RemediationGenerator
from vibe_guard.report.builder import build_report
from vibe_guard.report.renderer import render_json, render_markdown
from vibe_guard.rules.loader import RulePack, RuleValidationError, load_rule_pack
from vibe_guard.rules.models import Family


def get_default_rules_dir() -> Path:
    """Resolve default rules directory from env, repo, or working directory."""
    env_dir = os.environ.get("VIBE_GUARD_RULES_DIR")
    if env_dir and Path(env_dir).is_dir():
        return Path(env_dir)

    repo_rules = Path(__file__).resolve().parents[2] / "rules"
    if repo_rules.is_dir() and (repo_rules / "pack.yaml").is_file():
        return repo_rules

    cwd_rules = Path.cwd() / "rules"
    if cwd_rules.is_dir() and (cwd_rules / "pack.yaml").is_file():
        return cwd_rules

    return repo_rules


def run_scan(args: argparse.Namespace) -> int:
    """Execute vibe-guard scan subcommand."""
    source: str = args.source
    rules_dir = Path(args.rules) if args.rules else get_default_rules_dir()
    caller_id = args.caller_id or "anonymous"
    no_llm: bool = args.no_llm
    scan_id = f"scan-{uuid.uuid4().hex[:8]}"
    start_time = time.monotonic()
    timestamp = datetime.now(UTC).isoformat()

    # 1. Load rule pack (E-RUL-* returns exit code 2)
    try:
        pack = load_rule_pack(rules_dir)
        if getattr(args, "families", None):
            fam_items = [f.strip() for f in args.families.split(",") if f.strip()]
            valid_enums = set()
            for f in fam_items:
                try:
                    valid_enums.add(Family(f))
                except ValueError:
                    sys.stderr.write(f"Famille inconnue : {f}\n")
                    return 2
            filtered_rules = [r for r in pack.rules if r.family in valid_enums]
            pack = RulePack(manifest=pack.manifest, rules=filtered_rules, directory=pack.directory)
    except (RuleValidationError, FileNotFoundError, Exception) as exc:
        sys.stderr.write(f"Erreur de chargement des règles : {exc}\n")
        return 2

    # 2. Ingestion & Scan inside ephemeral workspace (C1, C2, E-ING-* returns exit code 2)
    findings = []
    target_display = source
    try:
        with EphemeralWorkspace() as ws:
            git_prefixes = ("https://", "http://", "git@", "ssh://")
            if source.startswith(git_prefixes) or source.endswith(".git"):
                scan_path = ws.clone_git(source, branch=args.branch)
            elif Path(source).is_file() and any(
                source.endswith(ext) for ext in [".zip", ".tar.gz", ".tgz", ".tar"]
            ):
                scan_path = ws.extract_archive(Path(source))
            elif Path(source).is_dir():
                scan_path = ws.copy_directory(Path(source))
            else:
                sys.stderr.write(
                    f"Erreur d'ingestion : source invalide ou introuvable : {source}\n"
                )
                return 2

            engine = ScanEngine(pack)
            findings = engine.scan(scan_path)
    except IngestionError as exc:
        sys.stderr.write(f"Erreur d'ingestion : {exc}\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"Erreur inattendue pendant l'ingestion/scan : {exc}\n")
        return 2

    duration_seconds = max(0.01, round(time.monotonic() - start_time, 2))

    # 3. Contextual remediation via LLM if enabled (C2, SPEC-REM-4 fallback)
    contextual_advices = {}
    prompt_version = None
    if not no_llm:
        try:
            generator = RemediationGenerator(enabled=True)
            prompt_version = generator.prompt_version
            contextual_advices = generator.enrich_findings(findings, rule_pack=pack)
        except Exception:
            contextual_advices = {}

    # 4. Build Report (SPEC-REP-1, SPEC-ENG-4, SPEC-REP-5)
    report = build_report(
        findings=findings,
        scan_id=scan_id,
        timestamp=timestamp,
        duration_seconds=duration_seconds,
        caller_id=caller_id,
        pack_version=pack.version,
        target=target_display,
        llm_remediation_enabled=not no_llm,
        prompt_version=prompt_version,
        contextual_advices=contextual_advices,
    )

    # 5. Record Audit (C6, SPEC-AUD-1, SPEC-AUD-2)
    try:
        audit_dir = Path(args.audit_dir) if args.audit_dir else None
        recorder = AuditRecorder(audit_dir=audit_dir)
        audit_record = ScanAuditRecord.from_scan(
            scan_id=scan_id,
            timestamp=timestamp,
            duration_seconds=duration_seconds,
            caller_id=caller_id,
            pack_version=pack.version,
            target=target_display,
            findings=findings,
            rules_evaluated=[r.id for r in pack.rules],
        )
        recorder.record(audit_record)
    except Exception:
        pass

    # 6. Render Output
    json_out = render_json(report)
    md_out = render_markdown(report)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fmt = args.format
        if fmt == "both":
            base = out_path.with_suffix("") if out_path.suffix in [".json", ".md"] else out_path
            base.with_suffix(".json").write_text(json_out, encoding="utf-8")
            base.with_suffix(".md").write_text(md_out, encoding="utf-8")
        elif fmt == "json":
            target_file = out_path if out_path.suffix == ".json" else out_path.with_suffix(".json")
            target_file.write_text(json_out, encoding="utf-8")
        else:
            target_file = out_path if out_path.suffix == ".md" else out_path.with_suffix(".md")
            target_file.write_text(md_out, encoding="utf-8")
    else:
        if args.format == "json":
            sys.stdout.write(json_out + "\n")
        else:
            sys.stdout.write(md_out + "\n")

    # 7. Determine Exit Code (Section 4.3, SPEC-ENG-4)
    # 3: degraded coverage, 1: findings detected, 0: clean
    if report.engine_status.coverage_degraded:
        return 3
    if len(report.findings) > 0:
        return 1
    return 0


def run_rules_validate(args: argparse.Namespace) -> int:
    """Execute vibe-guard rules validate subcommand."""
    rules_dir = Path(args.rules) if args.rules else get_default_rules_dir()
    try:
        pack = load_rule_pack(rules_dir)
        msg = (
            f"✅ Pack '{pack.manifest.name}' v{pack.manifest.version} valide "
            f"({len(pack.rules)} règles chargées).\n"
        )
        sys.stdout.write(msg)
        return 0
    except RuleValidationError as exc:
        sys.stderr.write(f"Erreur de validation de règles :\n{exc}\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"Erreur : {exc}\n")
        return 2


def run_rules_list(args: argparse.Namespace) -> int:
    """Execute vibe-guard rules list subcommand."""
    rules_dir = Path(args.rules) if args.rules else get_default_rules_dir()
    try:
        pack = load_rule_pack(rules_dir)
        rules = pack.rules
        if args.family:
            try:
                family_enum = Family(args.family)
                rules = pack.by_family(family_enum)
            except ValueError:
                sys.stderr.write(f"Famille inconnue : {args.family}\n")
                return 2

        sys.stdout.write(f"{'ID':<14} {'Famille':<10} {'Sévérité':<10} Titre\n")
        sys.stdout.write(f"{'-' * 14} {'-' * 10} {'-' * 10} {'-' * 50}\n")
        for r in sorted(rules, key=lambda x: (x.family.value, x.id)):
            sys.stdout.write(f"{r.id:<14} {r.family.value:<10} {r.severity.value:<10} {r.title}\n")
        return 0
    except Exception as exc:
        sys.stderr.write(f"Erreur lors du listage des règles : {exc}\n")
        return 2


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="vibe-guard",
        description="Vibe Guard — Agent d'industrialisation et de sécurité du vibe coding",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # vibe-guard scan <source>
    scan_parser = subparsers.add_parser("scan", help="Scanner une source de code")
    scan_parser.add_argument(
        "source", help="Chemin local, archive (.zip, .tar.gz) ou URL Git HTTPS"
    )
    scan_parser.add_argument("--branch", "-b", help="Branche Git à analyser")
    scan_parser.add_argument(
        "--rules", "--rules-pack", "-r", dest="rules", help="Répertoire du pack de règles"
    )
    scan_parser.add_argument(
        "--families",
        help="Familles de règles à évaluer (séparées par des virgules, ex: AUTH,SECRETS)",
    )
    scan_parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Désactiver l'enrichissement par LLM (remédiation statique pure)",
    )
    scan_parser.add_argument(
        "--format",
        choices=["json", "markdown", "both"],
        default="markdown",
        help="Format du rapport de sortie (défaut: markdown)",
    )
    scan_parser.add_argument(
        "--out",
        "--out-file",
        "-o",
        dest="out",
        help="Chemin du fichier ou préfixe d'enregistrement du rapport",
    )
    scan_parser.add_argument("--caller-id", help="Identité de l'appelant pour le journal d'audit")
    scan_parser.add_argument("--audit-dir", help="Répertoire de stockage des traces d'audit")

    # vibe-guard rules [validate|list]
    rules_parser = subparsers.add_parser("rules", help="Gestion et inspection des règles")
    rules_sub = rules_parser.add_subparsers(dest="rules_action", required=True)

    val_parser = rules_sub.add_parser("validate", help="Valider la conformité d'un pack de règles")
    val_parser.add_argument(
        "--rules", "--rules-pack", "-r", dest="rules", help="Répertoire du pack de règles à valider"
    )

    list_parser = rules_sub.add_parser("list", help="Lister les règles disponibles")
    list_parser.add_argument(
        "--rules", "--rules-pack", "-r", dest="rules", help="Répertoire du pack de règles"
    )
    list_parser.add_argument(
        "--family",
        "-f",
        choices=["AUTH", "SECRETS", "LLM-GOV", "NET-ISO"],
        help="Filtrer par famille",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for vibe-guard CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "scan":
        return run_scan(args)
    if args.subcommand == "rules":
        if args.rules_action == "validate":
            return run_rules_validate(args)
        if args.rules_action == "list":
            return run_rules_list(args)

    return 2


if __name__ == "__main__":
    sys.exit(main())
