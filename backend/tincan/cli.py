"""`tincan` command line: serve, seed-demo, render-prompts, backup-done."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from tincan import backup, store
from tincan.config import Config
from tincan.db import Database
from tincan.models import Contact, Feature
from tincan.schemas import Settings
from tincan.tts import prompts
from tincan.tts.piper import Tts


def cmd_serve(config: Config, args: argparse.Namespace) -> int:
    import uvicorn

    from tincan.main import create_app

    uvicorn.run(
        create_app(config), host=config.tincan_host, port=config.tincan_port, log_level="info"
    )
    return 0


def seed_demo(db: Database) -> None:
    with db.session() as s:
        if s.get(Contact, 1) is None:
            s.add(Contact(name="Mom", spoken_name="Mom", number="+15555550101", speed_dial=1))
            s.add(
                Contact(
                    name="Grandma", spoken_name="Grandma Jo", number="+15555550123", speed_dial=2
                )
            )
        for digit, kind, cfg in (
            (6, "weather", {}),
            (7, "fun_fact", {"topic": "dinosaurs"}),
            (8, "secret_message", {"recipient": "Mom"}),
            (9, "mailbox", {}),
        ):
            if s.get(Feature, digit) is None:
                s.add(Feature(digit=digit, kind=kind, config=json.dumps(cfg), enabled=True))
    store.save_settings(db, Settings())


def cmd_seed_demo(config: Config, args: argparse.Namespace) -> int:
    config.ensure_dirs()
    db = Database(config.db_path)
    db.migrate()
    seed_demo(db)
    print(f"seeded demo data into {config.db_path}")
    return 0


def cmd_render_prompts(config: Config, args: argparse.Namespace) -> int:
    config.ensure_dirs()
    db = Database(config.db_path)
    db.migrate()
    tts = Tts(config.prompts_dir, config.piper_bin, config.piper_voice, config.piper_data_dir)
    texts = list(prompts.STATIC.values())
    with db.session() as s:
        from sqlalchemy import select

        for c in s.scalars(select(Contact)):
            texts += [
                prompts.CALLING.format(name=c.spoken_name),
                prompts.NO_ANSWER.format(name=c.spoken_name),
                prompts.BUSY.format(name=c.spoken_name),
                prompts.NOT_ALLOWED.format(name=c.spoken_name),
            ]

    async def run() -> None:
        for t in texts:
            path = await tts.render(t)
            print(path.name, t)

    asyncio.run(run())
    if not tts.available:
        print("warning: piper not found, prompts are beeps", file=sys.stderr)
    return 0


def cmd_backup_done(config: Config, args: argparse.Namespace) -> int:
    db = Database(config.db_path)
    db.migrate()
    n = backup.mark_done(db, args.ids, ok=True)
    print(f"marked {n} recording(s) backed up")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    p = argparse.ArgumentParser(prog="tincan")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="run the API (0.0.0.0:8080)").set_defaults(fn=cmd_serve)
    sub.add_parser("seed-demo", help="create demo contacts, features and settings").set_defaults(
        fn=cmd_seed_demo
    )
    sub.add_parser("render-prompts", help="pre-render every static prompt with Piper").set_defaults(
        fn=cmd_render_prompts
    )
    bd = sub.add_parser("backup-done", help="mark recordings as backed up")
    bd.add_argument("ids", type=int, nargs="+")
    bd.set_defaults(fn=cmd_backup_done)
    args = p.parse_args(argv)
    return args.fn(Config(), args)


if __name__ == "__main__":
    sys.exit(main())
