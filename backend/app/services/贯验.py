import json

from app.db import 连接
from app.seed import 此刻

链接表 = ("链接_号卡套餐", "链接_号卡客户")


def 正式链接哈希集(conn) -> set[str]:
    return {
        r["哈希键"]
        for t in 链接表
        for r in conn.execute(f"SELECT 哈希键 FROM {t}")
    }


def 成功覆盖哈希(conn) -> set[str]:
    """成功回执覆盖的链接哈希：这些链接落正式库属合法，不算拒绝批残留。"""
    覆盖: set[str] = set()
    for r in conn.execute("SELECT 涉及链接哈希 FROM 装载回执 WHERE 结果='成功'"):
        覆盖 |= set(json.loads(r["涉及链接哈希"] or "[]"))
    return 覆盖


def 拒绝批残留(conn, 批号: str | None = None) -> list[str]:
    """架构甲巡检：被拒批次派生的链接哈希不得出现在正式链接，
    除非已被某个成功批次的回执覆盖（齐枢纽后重灌过闸的合法落库）。"""
    sql = "SELECT 批号, 涉及链接哈希 FROM 装载回执 WHERE 结果='拒绝'"
    参: tuple = ()
    if 批号 is not None:
        sql += " AND 批号=?"
        参 = (批号,)
    正式 = 正式链接哈希集(conn)
    覆盖 = 成功覆盖哈希(conn)
    残留 = []
    for r in conn.execute(sql, 参):
        for h in json.loads(r["涉及链接哈希"] or "[]"):
            if h in 正式 and h not in 覆盖:
                残留.append(f"{r['批号']}:{h}")
    return 残留


def 跑贯验() -> dict:
    conn = 连接()
    try:
        枢纽数 = sum(
            conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
            for t in ("枢纽_号卡", "枢纽_套餐", "枢纽_客户")
        )
        链接数 = sum(
            conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
            for t in 链接表
        )
        卫星当前数 = sum(
            conn.execute(f"SELECT COUNT(*) AS c FROM {t} WHERE 是否当前=1").fetchone()["c"]
            for t in ("卫星_号卡属性", "卫星_套餐属性", "卫星_客户属性", "卫星_订购属性")
        )

        缺链 = []
        for r in conn.execute("SELECT * FROM 链接_号卡套餐"):
            if not conn.execute("SELECT 1 FROM 枢纽_号卡 WHERE 哈希键=?", (r["号卡哈希"],)).fetchone():
                缺链.append(f"订购链缺号卡枢纽:{r['哈希键']}")
            if not conn.execute("SELECT 1 FROM 枢纽_套餐 WHERE 哈希键=?", (r["套餐哈希"],)).fetchone():
                缺链.append(f"订购链缺套餐枢纽:{r['哈希键']}")
        for r in conn.execute("SELECT * FROM 链接_号卡客户"):
            if not conn.execute("SELECT 1 FROM 枢纽_号卡 WHERE 哈希键=?", (r["号卡哈希"],)).fetchone():
                缺链.append(f"实名链缺号卡:{r['哈希键']}")
            if not conn.execute("SELECT 1 FROM 枢纽_客户 WHERE 哈希键=?", (r["客户哈希"],)).fetchone():
                缺链.append(f"实名链缺客户:{r['哈希键']}")

        孤儿 = []
        for 表, 列, 父表 in (
            ("卫星_号卡属性", "号卡哈希", "枢纽_号卡"),
            ("卫星_套餐属性", "套餐哈希", "枢纽_套餐"),
            ("卫星_客户属性", "客户哈希", "枢纽_客户"),
            ("卫星_订购属性", "链接哈希", "链接_号卡套餐"),
        ):
            for r in conn.execute(f"SELECT {列} AS p FROM {表} WHERE 是否当前=1"):
                if not conn.execute(f"SELECT 1 FROM {父表} WHERE 哈希键=?", (r["p"],)).fetchone():
                    孤儿.append(f"{表}:{r['p']}")

        双当前 = []
        for 表, 列 in (
            ("卫星_号卡属性", "号卡哈希"),
            ("卫星_套餐属性", "套餐哈希"),
            ("卫星_客户属性", "客户哈希"),
            ("卫星_订购属性", "链接哈希"),
        ):
            for r in conn.execute(
                f"SELECT {列} AS p, COUNT(*) AS c FROM {表} WHERE 是否当前=1 GROUP BY {列} HAVING c>1"
            ):
                双当前.append(f"{表}:{r['p']}")

        # 架构甲：贯验只做巡检，证明正式库无缺端残留，不补做装载闸、不做晋升
        残留 = 拒绝批残留(conn)

        检项 = [
            {
                "名": "链接两端可解",
                "通过": len(缺链) == 0,
                "说明": "全部链接两端枢纽可解" if not 缺链 else "；".join(缺链[:6]),
            },
            {
                "名": "卫星无孤儿",
                "通过": len(孤儿) == 0,
                "说明": "当前卫星均挂到合法父键" if not 孤儿 else "；".join(孤儿[:6]),
            },
            {
                "名": "无双当前",
                "通过": len(双当前) == 0,
                "说明": "同父键仅一条当前卫星" if not 双当前 else "；".join(双当前[:6]),
            },
            {
                "名": "缺端拒绝无残留",
                "通过": len(残留) == 0,
                "说明": (
                    "被拒批次在正式链接零残留（架构甲·装载期硬拒绝）"
                    if not 残留
                    else "；".join(残留[:6])
                ),
            },
        ]
        问题 = (
            缺链
            + [f"孤儿卫星:{x}" for x in 孤儿]
            + [f"双当前:{x}" for x in 双当前]
            + [f"缺端残留:{x}" for x in 残留]
        )
        通过 = 0 if 问题 else 1
        说明 = "；".join(问题) if 问题 else "枢纽、链接、卫星引用与当前版贯穿互证通过"
        conn.execute(
            "INSERT INTO 金库贯验(时刻, 枢纽数, 链接数, 卫星当前数, 是否通过, 说明) VALUES (?,?,?,?,?,?)",
            (此刻(), 枢纽数, 链接数, 卫星当前数, 通过, 说明),
        )
        conn.commit()
        return {
            "是否通过": bool(通过),
            "枢纽数": 枢纽数,
            "链接数": 链接数,
            "卫星当前数": 卫星当前数,
            "说明": 说明,
            "检项": 检项,
        }
    finally:
        conn.close()


def 查缺端批(批号: str) -> dict | None:
    """缺端贯验只读接口：批号 → 缺端键 / 正式链接增量 / 候选·拒绝位。

    架构甲口径：不设候选区，拒绝即终态（隔离匣），正式链接增量只认成功回执；
    被拒载荷不可晋升，唯一出路是补齐枢纽后同批号重灌过闸。
    """
    conn = 连接()
    try:
        回执 = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM 装载回执 WHERE 批号=? ORDER BY 编号", (批号,)
            )
        ]
        隔离 = [
            dict(r)
            for r in conn.execute(
                "SELECT 编号, 时刻, 原因 FROM 隔离匣 WHERE 批号=? ORDER BY 编号", (批号,)
            )
        ]
        if not 回执 and not 隔离:
            return None

        for r in 回执:
            r["缺端键"] = json.loads(r["缺端键"] or "[]")
            r["涉及链接哈希"] = json.loads(r["涉及链接哈希"] or "[]")

        最新 = 回执[-1] if 回执 else None
        成功回执 = [r for r in 回执 if r["结果"] == "成功"]
        拒绝中 = bool(最新 and 最新["结果"] == "拒绝")

        残留 = 拒绝批残留(conn, 批号)
        return {
            "批号": 批号,
            "架构": "甲·装载期硬拒绝",
            "最新回执": (
                {"结果": 最新["结果"], "时刻": 最新["时刻"], "说明": 最新["说明"]}
                if 最新
                else None
            ),
            # 当前态口径：最新回执为拒绝时缺端键为当前阻塞；已重灌成功则为空（履历留痕）
            "缺端键": 最新["缺端键"] if 拒绝中 else [],
            "正式链接增量": 成功回执[-1]["链接落库数"] if 成功回执 else 0,
            "候选位": None,  # 架构甲不设候选区
            "拒绝位": (
                {
                    "位置": "隔离匣",
                    "隔离匣编号": 隔离[-1]["编号"] if 隔离 else None,
                    "回执编号": 最新["编号"],
                    "终态": True,
                    "说明": "拒绝即终态，不可晋升；补齐枢纽后同批号重灌过闸",
                }
                if 拒绝中
                else None
            ),
            "残留巡检": {
                "正式残留": 残留,
                "是否干净": not 残留,
            },
            "履历": [
                {
                    "回执编号": r["编号"],
                    "时刻": r["时刻"],
                    "结果": r["结果"],
                    "链接落库数": r["链接落库数"],
                    "缺端键": r["缺端键"],
                    "说明": r["说明"],
                }
                for r in 回执
            ],
        }
    finally:
        conn.close()
