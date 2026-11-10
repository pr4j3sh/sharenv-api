"""Re-encrypt stored data under the active master key version.

Walks every project, re-wraps its data key under the active master key
version, and re-encrypts every variable value so its `key_version` and AAD
match. Idempotent and resumable: documents already on the active version are
skipped, so a crashed run can simply be re-run.

Runbook: docs/key-rotation.md

Usage (from the repository root, so `.env` is loaded):

    uv run python -m scripts.rotate_keys --dry-run
    uv run python -m scripts.rotate_keys
"""

import argparse
import asyncio
import sys

from app.core.config import settings
from app.core.crypto import decrypt_value, encrypt_value, unwrap_data_key, wrap_data_key
from app.core.logger import get_logger
from app.db.mongodb import mongo

log = get_logger(__name__)


async def rotate(dry_run: bool) -> int:
    await mongo.connect()
    try:
        return await _rotate(dry_run)
    finally:
        await mongo.close()


async def _rotate(dry_run: bool) -> int:
    if mongo.projects is None or mongo.environments is None or mongo.variables is None:
        raise RuntimeError("mongodb is not connected")

    active = settings.ENCRYPTION_KEY_VERSION
    log.info(
        "active master key version: %s%s", active, " (dry run)" if dry_run else ""
    )

    counts = {
        "projects_rewrapped": 0,
        "projects_current": 0,
        "variables_reencrypted": 0,
        "variables_current": 0,
        "failed": 0,
    }

    projects = await mongo.projects.find({}).to_list(length=None)
    known_env_ids: set[str] = set()

    for project in projects:
        project_id = str(project["_id"])

        try:
            data_key = unwrap_data_key(project["data_key"], project["key_version"])
        except Exception:
            counts["failed"] += 1
            log.error(
                "project %s: cannot unwrap data key under version %s; keep that"
                " master key in the registry and re-run",
                project_id,
                project.get("key_version"),
            )
            continue

        if project["key_version"] != active:
            if dry_run:
                log.info(
                    "[dry-run] project %s: re-wrap data key from version %s to %s",
                    project_id,
                    project["key_version"],
                    active,
                )
            else:
                res = await mongo.projects.update_one(
                    {"_id": project["_id"]},
                    {
                        "$set": {
                            "data_key": wrap_data_key(data_key),
                            "key_version": active,
                        }
                    },
                )
                if not res.acknowledged:
                    counts["failed"] += 1
                    log.error("project %s: failed to update wrapped data key", project_id)
                    continue

            counts["projects_rewrapped"] += 1
        else:
            counts["projects_current"] += 1

        environments = await mongo.environments.find(
            {"project_id": project_id}
        ).to_list(length=None)

        env_ids = [str(environment["_id"]) for environment in environments]
        known_env_ids.update(env_ids)

        variables = (
            await mongo.variables.find({"environment_id": {"$in": env_ids}}).to_list(
                length=None
            )
            if env_ids
            else []
        )

        for variable in variables:
            if variable["key_version"] == active:
                counts["variables_current"] += 1
                continue

            try:
                value = decrypt_value(
                    variable["value_enc"],
                    data_key,
                    project_id,
                    variable["environment_id"],
                    variable["name"],
                    variable["key_version"],
                )
            except Exception:
                counts["failed"] += 1
                log.exception(
                    "variable %s (%s): cannot decrypt under version %s; skipping",
                    variable["name"],
                    variable["_id"],
                    variable["key_version"],
                )
                continue

            if dry_run:
                log.info(
                    "[dry-run] variable %s: re-encrypt from version %s to %s",
                    variable["name"],
                    variable["key_version"],
                    active,
                )
            else:
                res = await mongo.variables.update_one(
                    {"_id": variable["_id"]},
                    {
                        "$set": {
                            "value_enc": encrypt_value(
                                value,
                                data_key,
                                project_id,
                                variable["environment_id"],
                                variable["name"],
                                active,
                            ),
                            "key_version": active,
                        }
                    },
                )
                if not res.acknowledged:
                    counts["failed"] += 1
                    log.error(
                        "variable %s (%s): failed to update",
                        variable["name"],
                        variable["_id"],
                    )
                    continue

            counts["variables_reencrypted"] += 1

    # Variables that belong to no environment can never be decrypted again;
    # report them instead of silently ignoring.
    orphans = await mongo.variables.find(
        {"environment_id": {"$nin": sorted(known_env_ids)}}
    ).to_list(length=None)
    for variable in orphans:
        log.warning(
            "orphaned variable %s (%s): no parent environment, not re-encrypted",
            variable["name"],
            variable["_id"],
        )

    log.info(
        "rotation %s: %d project(s) re-wrapped, %d already current;"
        " %d variable(s) re-encrypted, %d already current;"
        " %d failure(s), %d orphaned",
        "planned" if dry_run else "complete",
        counts["projects_rewrapped"],
        counts["projects_current"],
        counts["variables_reencrypted"],
        counts["variables_current"],
        counts["failed"],
        len(orphans),
    )

    return 1 if counts["failed"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Re-encrypt stored data under the active master key version"
            " (runbook: docs/key-rotation.md)"
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change without writing anything",
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(rotate(args.dry_run)))


if __name__ == "__main__":
    main()
