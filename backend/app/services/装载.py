import json
import uuid
from typing import Any

from app.db import 连接
from app.modules import 枢纽先于链接 as 缺端闸
from app.seed import 哈希键, 载荷哈希, 此刻


def 记回执(conn, 批号, 结果, 缺端键=None, 链接落库数=0, 涉及链接哈希=None, 说明=""):
    """装载回执：每批成败留痕，缺端贯验只读接口以此为准。架构甲不设候选区。"""
    conn.execute(
        "INSERT INTO 装载回执(批号, 时刻, 结果, 缺端键, 链接落库数, 涉及链接哈希, 说明)"
        " VALUES (?,?,?,?,?,?,?)",
        (
            批号,
            此刻(),
            结果,
            json.dumps(缺端键 or [], ensure_ascii=False),
            链接落库数,
            json.dumps(涉及链接哈希 or [], ensure_ascii=False),
            说明,
        ),
    )


def 装一批(体: dict[str, Any]) -> dict[str, Any]:
    """顺序：枢纽 → 链接 → 卫星。失败整批回滚。

    架构甲·装载期硬拒绝：落库前先过缺端写闸（枢纽先于链接），任一链接缺端
    或卫星缺父 → 整批拒绝，正式表零写入，载荷进隔离匣（拒绝位·终态），
    回执记「拒绝」；不设候选区，不做贯验晋升，补齐枢纽后同批号重灌过闸。
    """
    装载日 = str(体.get("装载日") or "").strip()
    枢纽 = 体.get("枢纽") or {}
    链接 = 体.get("链接") or {}
    卫星 = 体.get("卫星") or {}
    if not 装载日:
        return {"结果": "拒绝", "说明": "缺装载日"}

    批号 = str(体.get("批次编号") or f"批-{uuid.uuid4().hex[:10]}")
    conn = 连接()
    报 = {"枢纽": 0, "链接": 0, "卫星": 0, "跳过": 0, "明细": []}
    预 = {"缺端": [], "涉及链接哈希": []}
    try:
        if conn.execute("SELECT 1 FROM 装载批次 WHERE 编号=?", (批号,)).fetchone():
            return {"结果": "拒绝", "说明": "批次编号已存在"}

        # 缺端写闸：落库前预检全批链接两端与卫星父键，缺端整批失败闭
        预 = 缺端闸.预检缺端(体, conn)
        if 预["缺端"]:
            说明 = "；".join(
                f"{d['类']}缺{d['位']}:{d['业务键']}" for d in 预["缺端"][:8]
            )
            cur = conn.execute(
                "INSERT INTO 隔离匣(原因, 载荷, 时刻, 批号) VALUES (?,?,?,?)",
                (f"缺端拒绝:{说明}", json.dumps(体, ensure_ascii=False)[:2000], 此刻(), 批号),
            )
            记回执(conn, 批号, "拒绝", 缺端键=预["缺端"],
                   涉及链接哈希=预["涉及链接哈希"], 说明=说明)
            conn.commit()
            return {
                "结果": "拒绝",
                "批次编号": 批号,
                "装载日": 装载日,
                "说明": f"缺端整批拒绝（架构甲·装载期硬拒绝）: {说明}",
                "缺端键": 预["缺端"],
                "隔离匣编号": cur.lastrowid,
            }

        # 枢纽
        for 类, 表, 前缀 in (
            ("号卡", "枢纽_号卡", "号卡"),
            ("套餐", "枢纽_套餐", "套餐"),
            ("客户", "枢纽_客户", "客户"),
        ):
            for 项 in 枢纽.get(类) or []:
                业务键 = str(项.get("业务键") or "").strip()
                if not 业务键:
                    报["跳过"] += 1
                    continue
                h = 哈希键(前缀, 业务键)
                旧 = conn.execute(f"SELECT 1 FROM {表} WHERE 业务键=?", (业务键,)).fetchone()
                if 旧:
                    报["跳过"] += 1
                    报["明细"].append({"类": f"枢纽-{类}", "业务键": 业务键, "结果": "已存在"})
                    continue
                conn.execute(
                    f"INSERT INTO {表}(哈希键, 业务键, 装载日) VALUES (?,?,?)",
                    (h, 业务键, 装载日),
                )
                报["枢纽"] += 1
                报["明细"].append({"类": f"枢纽-{类}", "业务键": 业务键, "哈希键": h, "结果": "新开"})

        def 取枢纽哈希(表, 业务键):
            r = conn.execute(f"SELECT 哈希键 FROM {表} WHERE 业务键=?", (业务键,)).fetchone()
            return r["哈希键"] if r else None

        # 链接 号卡-套餐
        for 项 in 链接.get("号卡套餐") or []:
            号 = str(项.get("号卡业务键") or "").strip()
            套 = str(项.get("套餐业务键") or "").strip()
            hk卡 = 取枢纽哈希("枢纽_号卡", 号)
            hk套 = 取枢纽哈希("枢纽_套餐", 套)
            if not hk卡 or not hk套:
                raise ValueError(f"链接号卡套餐缺枢纽: {号}/{套}")
            lh = 哈希键("链订购", hk卡, hk套)
            if conn.execute("SELECT 1 FROM 链接_号卡套餐 WHERE 哈希键=?", (lh,)).fetchone():
                报["跳过"] += 1
                continue
            conn.execute(
                "INSERT INTO 链接_号卡套餐(哈希键, 号卡哈希, 套餐哈希, 装载日) VALUES (?,?,?,?)",
                (lh, hk卡, hk套, 装载日),
            )
            报["链接"] += 1

        # 链接 号卡-客户
        for 项 in 链接.get("号卡客户") or []:
            号 = str(项.get("号卡业务键") or "").strip()
            客 = str(项.get("客户业务键") or "").strip()
            hk卡 = 取枢纽哈希("枢纽_号卡", 号)
            hk客 = 取枢纽哈希("枢纽_客户", 客)
            if not hk卡 or not hk客:
                raise ValueError(f"链接号卡客户缺枢纽: {号}/{客}")
            lh = 哈希键("链实名", hk卡, hk客)
            if conn.execute("SELECT 1 FROM 链接_号卡客户 WHERE 哈希键=?", (lh,)).fetchone():
                报["跳过"] += 1
                continue
            conn.execute(
                "INSERT INTO 链接_号卡客户(哈希键, 号卡哈希, 客户哈希, 装载日) VALUES (?,?,?,?)",
                (lh, hk卡, hk客, 装载日),
            )
            报["链接"] += 1

        def 开卫星(表, 父列, 父哈希, 属性: dict):
            ph = 载荷哈希(属性)
            当前 = conn.execute(
                f"SELECT 编号, 载荷哈希 FROM {表} WHERE {父列}=? AND 是否当前=1",
                (父哈希,),
            ).fetchone()
            if 当前 and 当前["载荷哈希"] == ph:
                报["跳过"] += 1
                return
            if 当前:
                conn.execute(f"UPDATE {表} SET 是否当前=0 WHERE 编号=?", (当前["编号"],))
            conn.execute(
                f"INSERT INTO {表}({父列}, 装载日, 载荷哈希, 属性, 是否当前) VALUES (?,?,?,?,1)",
                (父哈希, 装载日, ph, json.dumps(属性, ensure_ascii=False)),
            )
            报["卫星"] += 1

        for 项 in 卫星.get("号卡") or []:
            号 = str(项.get("业务键") or "").strip()
            h = 取枢纽哈希("枢纽_号卡", 号)
            if not h:
                raise ValueError(f"卫星号卡无枢纽: {号}")
            开卫星("卫星_号卡属性", "号卡哈希", h, 项.get("属性") or {})

        for 项 in 卫星.get("套餐") or []:
            套 = str(项.get("业务键") or "").strip()
            h = 取枢纽哈希("枢纽_套餐", 套)
            if not h:
                raise ValueError(f"卫星套餐无枢纽: {套}")
            开卫星("卫星_套餐属性", "套餐哈希", h, 项.get("属性") or {})

        for 项 in 卫星.get("客户") or []:
            客 = str(项.get("业务键") or "").strip()
            h = 取枢纽哈希("枢纽_客户", 客)
            if not h:
                raise ValueError(f"卫星客户无枢纽: {客}")
            开卫星("卫星_客户属性", "客户哈希", h, 项.get("属性") or {})

        for 项 in 卫星.get("订购") or []:
            号 = str(项.get("号卡业务键") or "").strip()
            套 = str(项.get("套餐业务键") or "").strip()
            hk卡 = 取枢纽哈希("枢纽_号卡", 号)
            hk套 = 取枢纽哈希("枢纽_套餐", 套)
            if not hk卡 or not hk套:
                raise ValueError(f"卫星订购无链接端: {号}/{套}")
            lh = 哈希键("链订购", hk卡, hk套)
            if not conn.execute("SELECT 1 FROM 链接_号卡套餐 WHERE 哈希键=?", (lh,)).fetchone():
                raise ValueError(f"卫星订购无链接: {号}/{套}")
            开卫星("卫星_订购属性", "链接哈希", lh, 项.get("属性") or {})

        conn.execute(
            "INSERT INTO 装载批次(编号, 装载日, 时刻, 报告) VALUES (?,?,?,?)",
            (批号, 装载日, 此刻(), json.dumps(报, ensure_ascii=False)),
        )
        记回执(conn, 批号, "成功", 链接落库数=报["链接"],
               涉及链接哈希=预["涉及链接哈希"], 说明="整批过闸落库")
        conn.commit()
        return {"结果": "成功", "批次编号": 批号, "装载日": 装载日, "报告": 报}
    except Exception as e:
        # 失败闭与架构甲一致：异常即整批回滚，正式表零残留，载荷进隔离匣
        conn.rollback()
        conn.execute(
            "INSERT INTO 隔离匣(原因, 载荷, 时刻, 批号) VALUES (?,?,?,?)",
            (str(e), json.dumps(体, ensure_ascii=False)[:2000], 此刻(), 批号),
        )
        记回执(conn, 批号, "失败", 涉及链接哈希=预["涉及链接哈希"], 说明=str(e))
        conn.commit()
        return {"结果": "失败", "批次编号": 批号, "说明": str(e)}
    finally:
        conn.close()
