# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClipInfo:
    index: int
    duration: float
    role: str


class SmartEditPlanner:
    """Music-driven edit planner for CatPaw MV.

    Roles:
      hero        face / iconic character shot
      performance walk / dance / flowing costume
      action      attack / movement / sword work
      impact      hit / destruction / result
      ending      poster / final close-up
      neutral     fallback
    """

    VALID_ROLES = {"hero", "performance", "action", "impact", "ending", "neutral"}

    def _section_kind(self, t: float, duration: float, chorus: list[dict]) -> str:
        if duration <= 0:
            return "verse"
        if t < min(5.0, duration * 0.08):
            return "intro"
        if t >= duration - min(6.0, duration * 0.10):
            return "outro"
        for c in chorus or []:
            start = float(c.get("start") or 0)
            end = float(c.get("end") or start)
            if start <= t < end:
                return "chorus"
            if max(0.0, start - 5.0) <= t < start:
                return "prechorus"
        return "verse"

    @staticmethod
    def _role_priority(section: str) -> list[str]:
        return {
            "intro": ["hero", "ending", "performance", "neutral", "action", "impact"],
            "verse": ["performance", "hero", "neutral", "action", "impact", "ending"],
            "prechorus": ["hero", "performance", "action", "neutral", "impact", "ending"],
            "chorus": ["action", "impact", "hero", "performance", "neutral", "ending"],
            "outro": ["ending", "hero", "performance", "neutral", "action", "impact"],
        }.get(section, ["neutral", "hero", "performance", "action", "impact", "ending"])

    @staticmethod
    def _segment_length(section: str, bpm: float | None, remaining: float) -> float:
        # Fast cuts in chorus, slower in intro/outro.
        if bpm and bpm > 0:
            beat = 60.0 / bpm
            bars = {
                "intro": 8,
                "verse": 8,
                "prechorus": 4,
                "chorus": 4,
                "outro": 8,
            }.get(section, 8)
            proposed = beat * bars
        else:
            proposed = {
                "intro": 3.2,
                "verse": 3.0,
                "prechorus": 2.2,
                "chorus": 1.8,
                "outro": 3.4,
            }.get(section, 2.8)
        proposed = max(1.1, min(4.5, proposed))
        return min(proposed, remaining)

    def _choose(self, clips: list[ClipInfo], section: str, counters: dict[str, int], last_idx: int | None) -> ClipInfo:
        by_role: dict[str, list[ClipInfo]] = {}
        for c in clips:
            by_role.setdefault(c.role, []).append(c)
        for role in self._role_priority(section):
            pool = by_role.get(role) or []
            if not pool:
                continue
            k = counters.get(role, 0)
            # avoid same clip twice when alternatives exist
            for offset in range(len(pool)):
                item = pool[(k + offset) % len(pool)]
                if len(pool) == 1 or item.index != last_idx:
                    counters[role] = k + offset + 1
                    return item
        # fallback
        item = clips[(sum(counters.values()) if counters else 0) % len(clips)]
        return item

    def plan(
        self,
        clip_durations: list[float],
        clip_roles: list[str] | None,
        music_analysis: dict | None,
        target_seconds: float,
    ) -> dict:
        if not clip_durations:
            raise ValueError("至少需要一支影片")
        roles = clip_roles or []
        clips: list[ClipInfo] = []
        for i, duration in enumerate(clip_durations):
            role = roles[i] if i < len(roles) else "neutral"
            if role not in self.VALID_ROLES:
                role = "neutral"
            clips.append(ClipInfo(i, max(0.2, float(duration)), role))

        analysis = music_analysis or {}
        bpm = analysis.get("bpm_estimate")
        try:
            bpm = float(bpm) if bpm else None
        except Exception:
            bpm = None
        chorus = list(analysis.get("chorus_candidates") or [])

        target = max(1.0, float(target_seconds))
        t = 0.0
        counters: dict[str, int] = {}
        source_offsets: dict[int, float] = {}
        last_idx = None
        timeline = []

        # Cap keeps pathological inputs from creating huge render graphs.
        while t < target - 0.02 and len(timeline) < 160:
            section = self._section_kind(t, target, chorus)
            seg_len = self._segment_length(section, bpm, target - t)
            clip = self._choose(clips, section, counters, last_idx)

            usable = max(0.2, clip.duration)
            if seg_len > usable:
                seg_len = usable

            start = source_offsets.get(clip.index, 0.0)
            if start + seg_len > usable:
                start = 0.0
            end = min(usable, start + seg_len)
            if end - start < 0.18:
                start = 0.0
                end = min(usable, max(0.18, seg_len))
            source_offsets[clip.index] = end + 0.12

            timeline.append({
                "timeline_start": round(t, 3),
                "timeline_end": round(t + (end - start), 3),
                "clip_index": clip.index,
                "role": clip.role,
                "section": section,
                "source_start": round(start, 3),
                "source_end": round(end, 3),
            })
            t += end - start
            last_idx = clip.index

        return {
            "target_seconds": round(target, 3),
            "bpm_estimate": bpm,
            "segment_count": len(timeline),
            "timeline": timeline,
            "role_counts": {
                role: sum(1 for x in timeline if x["role"] == role)
                for role in sorted(self.VALID_ROLES)
            },
        }
