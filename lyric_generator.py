# -*- coding: utf-8 -*-
"""
Original lyric / character-theme generator for AI Music Studio v2.
All presets are original and do not copy existing puppet-theatre lyrics.
"""
from __future__ import annotations
import random

PROFILES = {
    "魔佛波旬": {
        "images": ["紫焰照破寂靜長夜", "黑蓮浮起萬丈魔光", "三界無聲只聞鐘鳴", "佛焰逆照天地邊界"],
        "powers": ["一念撼動六道", "掌中翻覆乾坤", "蓮火吞沒塵世", "魔光劃破天穹"],
        "hooks": ["魔佛降世　天地無聲", "黑蓮一開　誰敢問天", "佛魔同體　逆轉乾坤"],
    },
    "月扇影喵": {
        "images": ["冷月映在黑色扇面", "孤影踏過銀白霜地", "夜風捲起滿城月華", "一扇輕開星河倒映"],
        "powers": ["扇影斬開月色", "清光封住長夜", "孤月化成萬刃", "一念鎮住風雪"],
        "hooks": ["月扇一開　萬影皆寂", "影落長夜　唯月不滅", "一扇清光　照破千劫"],
    },
    "白狂天喵": {
        "images": ["白影踏過風雪長原", "寒光映著孤高身影", "長刀未鳴風已止息", "雪夜之上戰意如火"],
        "powers": ["刀光劈開長空", "一斬震碎封印", "狂意撼動山河", "寒鋒逆破天命"],
        "hooks": ["白狂一刀　天地退讓", "刀出如雪　戰意如雷", "孤身一戰　不問歸還"],
    },
    "焚天赤焰喵": {
        "images": ["赤焰燃過天際盡頭", "火光照亮破碎戰場", "焚風捲起漫天星火", "赤紅身影踏火而來"],
        "powers": ["火龍破十方", "烈焰吞天裂地", "焚火震碎夜幕", "赤炎翻湧九霄"],
        "hooks": ["焚天一怒　萬火同燃", "赤焰不滅　戰到天明", "火龍破界　十方皆震"],
    },
    "歲璃喵": {
        "images": ["時間停在雨幕之中", "金色波紋穿過長夜", "古老刀鞘輕敲地面", "歲月在她身後凝結"],
        "powers": ["一念停住光陰", "時間波紋逆轉戰局", "歲月之力封住萬劍", "一瞬改寫前後因果"],
        "hooks": ["三息之間　天地靜止", "歲璃一念　時光回首", "一敲刀鞘　萬象重排"],
    },
}

MODE = {
    "intro": {"titles": ["登場", "現影", "初臨"], "lines": ["今夜由她寫下第一聲", "一步踏入萬眾目光", "名字從此留在風中"]},
    "battle": {"titles": ["破陣", "武極", "裂天"], "lines": ["戰鼓一響便不再回頭", "招式交錯撕開夜幕", "此戰只問誰能站到最後"]},
    "ballad": {"titles": ["月下", "心聲", "流光"], "lines": ["有些名字只適合留在月光裡", "風帶走故事卻帶不走思念", "最深的話藏在最安靜的夜"]},
    "final": {"titles": ["天命", "終戰", "末劫"], "lines": ["若此戰就是最後一頁", "天地都在等最後答案", "今日之後再無退路"]},
}

OPEN = ["風從遠方帶來未完的夢", "夜色沉下　天地只剩心跳", "舊日的名字仍留在風中", "長路無聲　腳步卻從未停止"]
PRE = ["若命運要我低頭", "若天地早寫好結局", "若前方只剩最後一條路", "若此身註定穿越風暴"]
ANSWER = ["我便用此心寫下答案", "那就親手改寫最後一頁", "我仍會向前一步", "便讓今夜成為新的開始"]
BRIDGE = ["也許世界從未給過答案", "真正的勝負從來不在刀劍", "當最後一道光穿過長夜", "到了無路可退的那一刻"]
ENDING = ["名字終將留在風中", "月光仍會照著來時的路", "故事還沒有真正結束", "天亮以前　此心不滅"]


class LyricGenerator:
    def _profile(self, name: str):
        if name in PROFILES:
            return PROFILES[name]
        return {
            "images": [f"{name}映在深夜月光", f"風穿過{name}的長路", f"{name}在星空下甦醒", f"遠方傳來{name}的回聲"],
            "powers": ["一念跨越長夜", "心火照亮前路", "信念撼動命運", "微光穿破黑暗"],
            "hooks": [f"{name}　此心不滅", f"{name}　逆風而行", f"{name}　照破長夜"],
        }

    def generate(self, character_name="月扇影喵", mode="battle", language="zh-TW", hook_strength="strong"):
        p = self._profile(character_name.strip() or "無名角色")
        m = MODE.get(mode, MODE["battle"])
        hook = random.choice(p["hooks"])
        if hook_strength == "max":
            chorus_head = f"{hook}\n{random.choice(p['hooks'])}\n{random.choice(p['powers'])}"
        elif hook_strength == "normal":
            chorus_head = hook
        else:
            chorus_head = f"{hook}\n{random.choice(p['powers'])}"

        is_tw = language == "taiwanese"
        is_mix = language == "mixed"

        if is_tw:
            chorus = f"""{chorus_head}
風雨若欲擋阮的路
阮就一念行到底
天地若問阮驚不驚
阮嘛袂放棄家己"""
            bridge = f"""{random.choice(BRIDGE)}
阮才知影真正的力量
毋是勝過別人
是袂放棄心內彼道光"""
        elif is_mix:
            chorus = f"""{chorus_head}
風雨若欲擋阮的路
我就一念行到底
天地若問阮驚不驚
我嘛袂放棄家己"""
            bridge = f"""{random.choice(BRIDGE)}
才明白真正的力量
毋是勝過別人
是不曾背離初心"""
        else:
            chorus = f"""{chorus_head}
若風雨擋住我的路
我就一念走到底
若天地問我是否畏懼
我也不讓此心熄滅"""
            bridge = f"""{random.choice(BRIDGE)}
才明白真正的力量
並不是擊敗誰
而是不曾背離初心"""

        title = f"{character_name}・{random.choice(m['titles'])}"
        full_lyrics = f"""【主歌一】
{random.choice(p['images'])}
{random.choice(OPEN)}
{random.choice(m['lines'])}
{random.choice(p['powers'])}

【預副歌】
{random.choice(PRE)}
{random.choice(ANSWER)}

【副歌】
{chorus}

【主歌二】
{random.choice(p['images'])}
{random.choice(OPEN)}
{random.choice(p['powers'])}
{random.choice(m['lines'])}

【橋段】
{bridge}

【最終副歌】
{chorus}

【尾聲】
{random.choice(ENDING)}"""

        return {
            "title": title,
            "character_name": character_name,
            "mode": mode,
            "language": language,
            "full_lyrics": full_lyrics,
            "music_prompt": "cinematic wuxia, original female character theme, memorable chorus, clear vocal, dramatic oriental instrumentation",
            "note": "台語模板採台文混合用字，正式發佈前建議由熟悉台語者校對發音與用字。",
        }
