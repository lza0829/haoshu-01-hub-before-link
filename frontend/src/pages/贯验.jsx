import React,{useEffect,useState} from "react";
import {递,取} from "../api.js";

export default function 贯验(){
  const [末,设末]=useState(null);
  const [史,设史]=useState([]);
  const [忙,设忙]=useState(false);
  const [批号,设批号]=useState("批-缺端-01");
  const [缺端报,设缺端报]=useState(null);
  const [缺端错,设缺端错]=useState("");

  const 刷=async()=>{
    const 列=await 取("/贯验");
    设史(列);
    return 列;
  };
  useEffect(()=>{
    刷().then(列=>{
      if(列[0]) 设末({
        是否通过:!!列[0].是否通过,
        枢纽数:列[0].枢纽数,
        链接数:列[0].链接数,
        卫星当前数:列[0].卫星当前数,
        说明:列[0].说明,
        检项:null,
      });
    });
  },[]);

  const 跑=async()=>{
    设忙(true);
    try{
      const r=await 递("/贯验",{});
      设末(r);
      await 刷();
    } finally { 设忙(false); }
  };

  const 查缺端=async()=>{
    设缺端错(""); 设缺端报(null);
    try{ 设缺端报(await 取("/贯验/缺端/"+encodeURIComponent(批号.trim()))); }
    catch(e){ 设缺端错(String(e.message||e)); }
  };

  return (<div>
    <h1 className="题">贯验</h1>
    <p className="述">沿枢纽 → 链接 → 卫星贯穿互证：两端可解、卫星有父、同父无双当前、缺端拒绝批正式零残留。架构甲·装载期硬拒绝：贯验只做巡检，不补做装载闸、不做晋升。</p>
    <div className="行">
      <button onClick={跑} disabled={忙}>{忙?"贯验中…":"跑贯验"}</button>
      <button className="次" onClick={刷}>刷新履历</button>
    </div>

    {!末 && <div className="空态">尚未跑过贯验，点上方按钮做一次全仓贯穿检查。</div>}

    {末 && <>
      <div className="裁决">
        <div className={`裁决旗 ${末.是否通过?"通":"败"}`}>
          <div className="标">{末.是否通过?"通过":"未过"}</div>
          <div className="辅">{末.说明}</div>
        </div>
        <div className="裁决数">
          <div className="卡"><b>{末.枢纽数}</b><span>枢纽</span></div>
          <div className="卡"><b>{末.链接数}</b><span>链接</span></div>
          <div className="卡"><b>{末.卫星当前数}</b><span>卫星当前</span></div>
        </div>
      </div>

      {末.检项?.length>0 && (
        <div className="段">
          <div className="段题">本轮检项</div>
          <div className="检列">
            {末.检项.map(x=>(
              <div className="检条" key={x.名}>
                <div className={`检点 ${x.通过?"通":"败"}`}>{x.通过?"✓":"!"}</div>
                <div className="检名">{x.名}</div>
                <div className="检说">{x.说明}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>}

    <div className="段">
      <div className="段题">缺端批查询（只读）</div>
      <div className="行">
        <input value={批号} onChange={e=>设批号(e.target.value)} placeholder="批号，如 批-缺端-01"/>
        <button className="次" onClick={查缺端} disabled={!批号.trim()}>查缺端</button>
      </div>
      {缺端错 && <div className="空态">查询失败：{缺端错}</div>}
      {缺端报 && (
        <div className="装载报">
          <div className="装载顶">
            <span className="批">{缺端报.批号}</span>
            <span className="徽章 淡">{缺端报.架构}</span>
            {缺端报.最新回执 && (
              <span className={`徽章 ${缺端报.最新回执.结果==="成功"?"通":"败"}`}>
                最新回执：{缺端报.最新回执.结果}
              </span>
            )}
            <span className={`徽章 ${缺端报.残留巡检.是否干净?"通":"败"}`}>
              {缺端报.残留巡检.是否干净?"正式零残留":"有正式残留"}
            </span>
          </div>
          <div className="格" style={{marginBottom:"0.85rem"}}>
            <div className="卡"><b>{缺端报.缺端键.length}</b><span>当前缺端键</span></div>
            <div className="卡"><b>{缺端报.正式链接增量}</b><span>正式链接增量</span></div>
            <div className="卡"><b>{缺端报.候选位? "有":"无"}</b><span>候选位（甲不设候选区）</span></div>
            <div className="卡"><b>{缺端报.拒绝位? "隔离匣#"+缺端报.拒绝位.隔离匣编号 :"—"}</b><span>拒绝位{缺端报.拒绝位?"（终态）":""}</span></div>
          </div>
          {缺端报.缺端键.length>0 && (
            <ul className="明细">
              {缺端报.缺端键.map((d,i)=>(
                <li key={i}><b>{d.类}</b> · 缺{d.位} · {d.业务键} · {d.说明}</li>
              ))}
            </ul>
          )}
          {缺端报.履历.length>0 && (
            <table>
              <thead><tr><th>回执</th><th>时刻</th><th>结果</th><th>链接落库</th><th>缺端数</th><th>说明</th></tr></thead>
              <tbody>{缺端报.履历.map(r=>(
                <tr key={r.回执编号}>
                  <td>{r.回执编号}</td><td>{r.时刻}</td>
                  <td><span className={`徽章 ${r.结果==="成功"?"通":"败"}`}>{r.结果}</span></td>
                  <td>{r.链接落库数}</td><td>{r.缺端键.length}</td><td>{r.说明}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      )}
    </div>

    <div className="段">
      <div className="段题">贯验履历</div>
      {!史.length ? <div className="空态">暂无记录</div> : (
        <table>
          <thead>
            <tr>
              <th>编号</th><th>时刻</th><th>枢纽</th><th>链接</th>
              <th>卫星当前</th><th>结果</th><th>说明</th>
            </tr>
          </thead>
          <tbody>
            {史.map(r=>(
              <tr key={r.编号}>
                <td>{r.编号}</td>
                <td>{r.时刻}</td>
                <td>{r.枢纽数}</td>
                <td>{r.链接数}</td>
                <td>{r.卫星当前数}</td>
                <td><span className={`徽章 ${r.是否通过?"通":"败"}`}>{r.是否通过?"通过":"未过"}</span></td>
                <td>{r.说明}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  </div>);
}
