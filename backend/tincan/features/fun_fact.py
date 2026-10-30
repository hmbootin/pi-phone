"""Random fact by topic from <data>/facts.json (seeded from facts_seed.json on first use)."""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tincan.features.base import Feature
from tincan.tts import prompts

if TYPE_CHECKING:
    from tincan.runtime import Runtime

SEED = Path(__file__).parent / "facts_seed.json"


def facts_file(data_dir: Path) -> Path:
    path = data_dir / "facts.json"
    if not path.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SEED, path)
    return path


def load_facts(data_dir: Path) -> dict[str, list[str]]:
    with facts_file(data_dir).open() as f:
        return json.load(f)


class FunFactFeature(Feature):
    kind = "fun_fact"

    def pick(self, data_dir: Path, topic: str | None) -> tuple[str, str]:
        facts = load_facts(data_dir)
        if topic not in facts or not facts[topic]:
            topic = random.choice([t for t, fs in facts.items() if fs])
        return topic, random.choice(facts[topic])

    async def text(self, rt: Runtime, config: dict[str, Any]) -> str:
        topic, fact = self.pick(rt.config.data_dir, config.get("topic"))
        return prompts.FUN_FACT.format(topic=topic, fact=fact)
