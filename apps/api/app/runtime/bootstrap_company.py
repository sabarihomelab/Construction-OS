import argparse
import asyncio
import json
from dataclasses import asdict

from app.db import model_registry  # noqa: F401
from app.db.session import SessionLocal
from app.modules.organizations.bootstrap import CompanyBootstrapError, bootstrap_initial_company


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create the first Construction OS company and protected administrator membership."
    )
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--company-slug", required=True)
    parser.add_argument("--legal-name")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-display-name", required=True)
    return parser


async def _run(args: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        try:
            result = await bootstrap_initial_company(
                db,
                company_name=args.company_name,
                company_slug=args.company_slug,
                legal_name=args.legal_name,
                admin_email=args.admin_email,
                admin_display_name=args.admin_display_name,
            )
            await db.commit()
        except CompanyBootstrapError as exc:
            await db.rollback()
            print(json.dumps({"status": "error", "detail": str(exc)}))
            return 2
        print(json.dumps({"status": "created", **asdict(result)}, sort_keys=True))
        return 0


def main() -> None:
    args = _parser().parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
