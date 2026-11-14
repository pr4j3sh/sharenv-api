import argparse
import asyncio
import sys

from app.core.config import settings
from app.core.crypto import decrypt_value, encrypt_value, unwrap_data_key, wrap_data_key
from app.core.logger import get_logger
from app.db.mongodb import mongo

log = get_logger(__name__)


async def rotate(dry_run: bool, allow_orphans: bool) -> int:
    await mongo.connect()
    try:
        return await _rotate(dry_run, allow_orphans)
    finally:
        await mongo.close()


async def _rotate(dry_run: bool, allow_orphans: bool) -> int:
    if mongo.projects is None or mongo.environments is None or mongo.variables is None:
        raise RuntimeError("mongodb is not connected")

    active = settings.ENCRYPTION_KEY_VERSION
    log.info("active master key version: %s%s", active, " (dry run)" if dry_run else "")

    counts = {
        "projects_rewrapped": 0,
        "projects_current": 0,
        "variables_reencrypted": 0,
        "variables_current": 0,
        "failed": 0,
        "planned": 0,
    }

    projects = await mongo.projects.find({}).to_list(length=None)
    known_env_ids: set[str] = set()

    for project in projects:
        env_ids = await _rotate_project(project, active, dry_run, counts)
        known_env_ids.update(env_ids)

    orphans = await mongo.variables.find(
        {"environment_id": {"$nin": sorted(known_env_ids)}}
    ).to_list(length=None)
    for variable in orphans:
        log.error(
            "orphaned variable %s (%s): no parent environment, not re-encrypted",
            variable["name"],
            variable["_id"],
        )

    if orphans and not allow_orphans:
        log.error(
            "refusing to proceed: %d orphaned variable(s) would remain undecryptable"
            " after rotation if the old key is removed from the registry;"
            " fix or remove them, or pass --allow-orphans",
            len(orphans),
        )
        return 1

    log.info(
        "rotation %s: %d project(s) re-wrapped, %d already current; "
        "%d variable(s) re-encrypted, %d already current; "
        "%d failure(s), %d orphaned",
        "planned" if dry_run else "complete",
        counts["projects_rewrapped"],
        counts["projects_current"],
        counts["variables_reencrypted"],
        counts["variables_current"],
        counts["failed"],
        len(orphans),
    )
    if dry_run:
        log.info("[dry-run] %d record(s) would change", counts["planned"])

    return 1 if counts["failed"] else 0


async def _rotate_project(
    project: dict, active: int, dry_run: bool, counts: dict[str, int]
) -> list[str]:
    assert mongo.environments is not None
    assert mongo.variables is not None

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
        return []

    if project["key_version"] != active:
        if dry_run:
            log.info(
                "[dry-run] project %s: re-wrap data key from version %s to %s",
                project_id,
                project["key_version"],
                active,
            )
            counts["planned"] += 1
        else:
            rewrapped = await _rewrap_project_key(
                project, data_key, project_id, counts, active
            )
            if not rewrapped:
                return []
            counts["projects_rewrapped"] += 1
    else:
        counts["projects_current"] += 1

    environments = await mongo.environments.find({"project_id": project_id}).to_list(
        length=None
    )

    env_ids = [str(environment["_id"]) for environment in environments]
    variables = (
        await mongo.variables.find({"environment_id": {"$in": env_ids}}).to_list(
            length=None
        )
        if env_ids
        else []
    )

    for variable in variables:
        await _rotate_variable(variable, active, project_id, data_key, dry_run, counts)

    return env_ids


async def _rewrap_project_key(
    project: dict,
    data_key: bytes,
    project_id: str,
    counts: dict[str, int],
    active: int,
) -> bool:
    if mongo.projects is None:
        raise RuntimeError("mongodb is not connected")

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
        return False

    try:
        updated = await mongo.projects.find_one(
            {"_id": project["_id"]}, {"data_key": 1, "key_version": 1}
        )
        if updated is None:
            raise RuntimeError("project vanished")
        verified = unwrap_data_key(updated["data_key"], updated["key_version"])
        if verified != data_key:
            raise RuntimeError("data key mismatch after re-wrap")
    except Exception:
        counts["failed"] += 1
        log.exception("project %s: failed read-back verification", project_id)
        return False

    return True


async def _rotate_variable(
    variable: dict,
    active: int,
    project_id: str,
    data_key: bytes,
    dry_run: bool,
    counts: dict[str, int],
) -> None:
    if mongo.variables is None:
        raise RuntimeError("mongodb is not connected")

    if variable["key_version"] == active:
        counts["variables_current"] += 1
        return

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
        return

    if dry_run:
        log.info(
            "[dry-run] variable %s: re-encrypt from version %s to %s",
            variable["name"],
            variable["key_version"],
            active,
        )
        counts["planned"] += 1
        return

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
        return

    try:
        updated = await mongo.variables.find_one(
            {"_id": variable["_id"]}, {"value_enc": 1, "key_version": 1}
        )
        if updated is None:
            raise RuntimeError("variable vanished")
        verified = decrypt_value(
            updated["value_enc"],
            data_key,
            project_id,
            variable["environment_id"],
            variable["name"],
            updated["key_version"],
        )
        if verified != value:
            raise RuntimeError("value mismatch after re-encryption")
    except Exception:
        counts["failed"] += 1
        log.exception(
            "variable %s (%s): failed read-back verification",
            variable["name"],
            variable["_id"],
        )
        return

    counts["variables_reencrypted"] += 1


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
    parser.add_argument(
        "--allow-orphans",
        action="store_true",
        help="do not fail when orphaned variables are found",
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(rotate(args.dry_run, args.allow_orphans)))


if __name__ == "__main__":
    main()
