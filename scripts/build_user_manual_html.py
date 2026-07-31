from __future__ import annotations

import argparse
import base64
import html
from pathlib import Path


def image_data(path: Path) -> str:
    mime = "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def figure(screens: Path, filename: str, caption: str) -> str:
    source = image_data(screens / filename)
    return (
        '<figure class="screen">'
        f'<a href="{source}" target="_blank" title="点击查看原图">'
        f'<img src="{source}" alt="{html.escape(caption)}"></a>'
        f"<figcaption>{html.escape(caption)} · 点击图片可查看原图</figcaption>"
        "</figure>"
    )


def build(screens: Path) -> str:
    login = figure(screens, "01-login.png", "企业化登录页")
    guide = figure(screens, "02-operation-guide.png", "内置操作引导")
    overview = figure(screens, "03-overview.png", "运营总览")
    dispatch = figure(screens, "04-fixed-dispatch.png", "固定智能调度方案")
    event = figure(screens, "06-event-after.png", "固定车辆故障处置完成")
    execution = figure(screens, "07-execution.png", "管理员执行中心")
    driver = figure(screens, "11-driver-execution.png", "驾驶员执行中心")
    ai = figure(screens, "08-ai-settings.png", "AI 服务连接管理")
    amap = figure(screens, "09-map-settings.png", "高德地图连接管理")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="祁智运县域物流智能决策平台图文使用手册">
  <title>祁智运平台图文使用手册</title>
  <style>
    :root {{
      --green:#0d5138; --green-2:#16764c; --mint:#eaf4ef; --yellow:#f5b83b;
      --ink:#17372b; --muted:#61736a; --line:#d8e3dd; --paper:#f4f7f5;
      --white:#fff; --warning:#fff5df; --danger:#fdeceb; --shadow:0 16px 45px rgba(13,81,56,.10);
    }}
    *{{box-sizing:border-box}} html{{scroll-behavior:smooth}}
    body{{margin:0;color:var(--ink);background:var(--paper);font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;line-height:1.75}}
    a{{color:inherit}} .layout{{display:grid;grid-template-columns:280px minmax(0,1fr);min-height:100vh}}
    aside{{position:sticky;top:0;height:100vh;padding:26px 20px;background:var(--green);color:#fff;overflow:auto}}
    .brand{{display:flex;align-items:center;gap:12px;margin-bottom:26px}} .mark{{display:grid;place-items:center;width:42px;height:42px;border-radius:12px;background:var(--yellow);color:var(--green);font-weight:900}}
    .brand strong{{font-size:20px}} .brand small{{display:block;color:#bfe0cf;letter-spacing:1.5px}}
    nav a{{display:block;padding:9px 12px;margin:3px 0;border-radius:9px;text-decoration:none;color:#dcece3;font-size:14px}}
    nav a:hover{{background:rgba(255,255,255,.12);color:#fff}} .side-note{{margin-top:25px;padding:14px;border:1px solid rgba(255,255,255,.16);border-radius:12px;color:#cfe5d9;font-size:12px}}
    main{{min-width:0}} .hero{{padding:68px clamp(24px,5vw,76px);color:#fff;background:linear-gradient(135deg,#0b4933,#126544)}}
    .hero .eyebrow{{color:var(--yellow);font-weight:800;letter-spacing:1px}} h1{{max-width:850px;margin:10px 0 14px;font-size:clamp(34px,5vw,66px);line-height:1.08;letter-spacing:-2px}}
    .hero p{{max-width:760px;color:#d9eee3;font-size:18px}} .chips{{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}}
    .chip{{padding:7px 12px;border:1px solid rgba(255,255,255,.2);border-radius:999px;background:rgba(255,255,255,.08);font-size:13px}}
    .content{{width:min(1120px,calc(100% - 40px));margin:34px auto 80px}} section{{scroll-margin-top:20px;margin:0 0 28px;padding:34px;background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}}
    .section-title{{display:flex;gap:16px;align-items:flex-start;margin-bottom:22px}} .num{{flex:0 0 auto;display:grid;place-items:center;width:52px;height:52px;border-radius:13px;background:var(--yellow);color:var(--green);font-size:19px;font-weight:900}}
    h2{{margin:0;font-size:28px;line-height:1.25}} h3{{margin:24px 0 8px;color:var(--green-2)}} .lead{{margin:4px 0 0;color:var(--muted)}}
    .callout{{margin:20px 0;padding:16px 18px;border-left:5px solid var(--green-2);border-radius:10px;background:var(--mint)}} .callout.warning{{border-color:#b36d00;background:var(--warning)}} .callout.danger{{border-color:#c94b43;background:var(--danger)}}
    .callout strong{{display:block;margin-bottom:4px;color:var(--green)}} ol,ul{{padding-left:24px}} li{{margin:7px 0}}
    .table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:12px}} table{{width:100%;border-collapse:collapse}} th,td{{padding:13px 15px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}} th{{background:var(--green);color:#fff}} tr:last-child td{{border-bottom:0}} td:first-child{{width:24%;font-weight:800;color:var(--green);background:#f5f8f6}}
    .screen{{margin:22px 0}} .screen a{{display:block;border:1px solid var(--line);border-radius:14px;overflow:hidden;background:#eef3f0}} .screen img{{display:block;width:100%;height:auto}} figcaption{{padding-top:8px;color:var(--muted);text-align:center;font-size:13px}}
    .accounts{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}} .account{{padding:18px;border-radius:12px;background:var(--mint)}} .account b{{display:block;color:var(--green)}} code{{padding:2px 6px;border-radius:5px;background:#edf1ef;font-family:Consolas,monospace}}
    .timeline{{display:grid;gap:10px}} .time-row{{display:grid;grid-template-columns:120px 1fr;gap:16px;padding:13px 15px;border:1px solid var(--line);border-radius:10px}} .time-row b{{color:var(--green)}}
    .top{{position:fixed;right:22px;bottom:22px;display:grid;place-items:center;width:44px;height:44px;border-radius:50%;background:var(--yellow);color:var(--green);font-weight:900;text-decoration:none;box-shadow:var(--shadow)}}
    footer{{padding:25px;color:var(--muted);text-align:center}}
    @media(max-width:900px){{.layout{{display:block}} aside{{position:relative;height:auto}} nav{{display:grid;grid-template-columns:repeat(2,1fr)}} .content{{width:min(100% - 24px,1120px)}} section{{padding:23px}} .accounts{{grid-template-columns:1fr}}}}
    @media print{{aside,.top{{display:none}} .layout{{display:block}} body{{background:#fff}} .hero{{padding:30px}} .content{{width:100%;margin:0}} section{{break-inside:avoid;box-shadow:none;border-radius:0;margin:0;padding:24px}} .screen a{{border:0}}}}
  </style>
</head>
<body id="top">
<div class="layout">
  <aside>
    <div class="brand"><span class="mark">祁</span><div><strong>祁智运</strong><small>AI LOGISTICS OS</small></div></div>
    <nav aria-label="手册目录">
      <a href="#quick">00 快速上手</a><a href="#start">01 启动与关闭</a><a href="#login">02 登录平台</a>
      <a href="#guide">03 操作引导</a><a href="#overview">04 运营总览</a><a href="#dispatch">05 固定调度</a>
      <a href="#event">06 故障处置</a><a href="#execution">07 执行闭环</a><a href="#driver">08 驾驶员</a>
      <a href="#config">09 服务配置</a><a href="#reset">10 一键恢复</a><a href="#script">11 讲解顺序</a>
      <a href="#faq">12 常见问题</a>
    </nav>
    <div class="side-note">单文件手册 · 图片已内嵌<br>可离线打开，可直接打印为 PDF。</div>
  </aside>
  <main>
    <header class="hero">
      <div class="eyebrow">祁智运 · 县域物流智能决策平台</div>
      <h1>图文使用手册</h1>
      <p>从一键启动、固定智能调度，到车辆故障处置与驾驶员执行。按页面顺序操作，不需要自行配置 Python、Node.js 或数据库。</p>
      <div class="chips"><span class="chip">标准运营基线 v1</span><span class="chip">12 个固定订单</span><span class="chip">5 辆固定车辆</span><span class="chip">固定路网快照</span><span class="chip">固定故障事件</span></div>
    </header>
    <div class="content">
      <section id="quick"><div class="section-title"><span class="num">00</span><div><h2>先看这一页</h2><p class="lead">不懂技术也可以完成一套完整操作</p></div></div>
        <div class="callout"><strong>最短操作路径</strong>双击“启动祁智运平台.bat” → 管理员登录 → 运营总览 → 生成今日调度 → 动态事件 → 启动处置 → 执行中心。</div>
        <div class="accounts"><div class="account"><b>管理员</b><code>admin</code> / <code>QizhiDemo2026!</code><br>全局调度、处置、审批和配置。</div><div class="account"><b>驾驶员</b><code>driver</code> / <code>DriverDemo2026!</code><br>只查看并执行本人任务。</div></div>
        <h3>平台解决的问题</h3><ul><li>统一处理订单、车辆容量、冷链、时间窗和班次约束。</li><li>使用 OR-Tools 生成可执行路线，并在真实地图上展示访问顺序。</li><li>车辆故障时冻结已执行任务，只重算剩余任务。</li><li>把调度结果转为审批、下发和驾驶员执行闭环。</li></ul>
        <div class="callout warning"><strong>为什么结果不会变化</strong>标准基线已固定订单、车辆、OSRM 路网矩阵、求解参数和故障事件。AI 可解释结果，但不会改变标准路线。</div>
      </section>

      <section id="start"><div class="section-title"><span class="num">01</span><div><h2>启动、检查与关闭</h2><p class="lead">四个批处理文件已经封装运行环境</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>文件</th><th>作用</th></tr></thead><tbody>
          <tr><td>启动祁智运平台.bat</td><td>自动启动 Docker Desktop、数据库、后端与页面，并打开浏览器。</td></tr>
          <tr><td>检查平台状态.bat</td><td>检查数据库、缓存、调度服务和页面。</td></tr>
          <tr><td>停止祁智运平台.bat</td><td>安全停止服务；业务数据和配置不会丢失。</td></tr>
          <tr><td>一键恢复标准演示数据.bat</td><td>先备份数据库，再恢复标准订单、车辆和事件；保留 AI 与高德配置。</td></tr>
        </tbody></table></div>
        <ol><li>电脑只需预装 Docker Desktop。</li><li>双击启动文件，等待“全部服务已经就绪”。</li><li>浏览器未自动打开时，访问 <code>http://127.0.0.1</code>。</li></ol>
        <div class="callout danger"><strong>不要删除 Docker 数据卷</strong>正常结束请使用停止文件。删除容器数据卷可能造成业务数据不可恢复。</div>
      </section>

      <section id="login"><div class="section-title"><span class="num">02</span><div><h2>登录平台</h2><p class="lead">管理员与驾驶员共用登录页，登录后按角色展示权限</p></div></div>{login}
        <ol><li>管理员使用 <code>admin</code> 登录。</li><li>驾驶员使用 <code>driver</code> 登录。</li><li>连续 5 次输入错误会锁定账号 15 分钟。</li></ol>
      </section>

      <section id="guide"><div class="section-title"><span class="num">03</span><div><h2>跟随内置操作引导</h2><p class="lead">第一次登录会高亮下一步入口</p></div></div>{guide}
        <ul><li>引导包含运营总览、生成调度、智能调度、动态事件和执行中心。</li><li>引导只切换页面，不会自动提交、审批或下发任务。</li><li>可点击顶栏“操作引导”再次打开。</li></ul>
      </section>

      <section id="overview"><div class="section-title"><span class="num">04</span><div><h2>读懂运营总览</h2><p class="lead">先确认需求、运力、路网与风险，再进入调度</p></div></div>{overview}
        <div class="table-wrap"><table><thead><tr><th>指标</th><th>含义</th></tr></thead><tbody>
          <tr><td>今日预测需求</td><td>固定业务样本的当日需求规模。</td></tr><tr><td>建议运力</td><td>按目标装载率和冷链需求计算的车辆数。</td></tr>
          <tr><td>路网矩阵</td><td>标准基线显示 OSRM，里程与时间来自固定路网快照。</td></tr><tr><td>预测准时率</td><td>当前约束下的可达成比例。</td></tr>
        </tbody></table></div>
      </section>

      <section id="dispatch"><div class="section-title"><span class="num">05</span><div><h2>生成固定调度方案</h2><p class="lead">重复操作得到相同路线与核心指标</p></div></div>{dispatch}
        <ol><li>从运营总览点击“生成今日调度”，或进入“智能调度”。</li><li>点击“重新生成方案”。</li><li>点击车辆卡片切换路线；地图编号是访问顺序。</li><li>查看综合评分与优化前后对比。</li></ol>
        <div class="callout"><strong>标准结果</strong>12 单、5 辆可用车，最终使用 3 辆车，订单服务率 100%；总里程约 339 km，预计成本约 1,196 元。</div>
      </section>

      <section id="event"><div class="section-title"><span class="num">06</span><div><h2>处理固定车辆故障</h2><p class="lead">湘D·A1234 在尚义村发生固定故障事件</p></div></div>{event}
        <ol><li>进入“动态事件”，点击“启动处置”。</li><li>系统识别 V-COLD-01（湘D·A1234）在尚义村故障。</li><li>冻结已完成节点，加入固定紧急订单并启用应急冷藏备用车。</li><li>确认事件识别、约束重建、增量求解、方案下发均已完成。</li></ol>
        <div class="callout warning"><strong>故障图标何时消失</strong>处置完成后状态变为“事件闭环”。仍有待处理红点时先刷新页面，必要时执行一键恢复。</div>
      </section>

      <section id="execution"><div class="section-title"><span class="num">07</span><div><h2>审批与执行闭环</h2><p class="lead">管理员确认方案，驾驶员接收并更新状态</p></div></div>{execution}
        <ul><li>管理员：查看方案 → 审核 → 批准并下发 → 监控执行。</li><li>驾驶员：接单 → 开始执行 → 逐站完成 → 完成路线。</li><li>审批、下发和状态变化都有记录。</li></ul>
        <div class="callout"><strong>管理员和驾驶员界面不同是正常的</strong>管理员查看县域全局；驾驶员只访问本人被授权的路线，避免越权读取其他车辆数据。</div>
      </section>

      <section id="driver"><div class="section-title"><span class="num">08</span><div><h2>驾驶员视角</h2><p class="lead">驾驶员不参与全局求解，只执行已下发任务</p></div></div>{driver}
        <ol><li>使用 <code>driver / DriverDemo2026!</code> 登录。</li><li>进入执行中心，确认车牌、节点顺序、预计到达时间和冷链标识。</li><li>按进度执行接单、出发、到站和完成。</li><li>未下发时显示空任务，这是正常状态。</li></ol>
      </section>

      <section id="config"><div class="section-title"><span class="num">09</span><div><h2>AI 与高德地图配置</h2><p class="lead">连接以企业化列表管理，密钥只显示掩码</p></div></div>
        <h3>AI 服务</h3>{ai}<ol><li>进入“系统设置 → AI 服务”，点击“新建连接”。</li><li>填写服务商、Base URL、模型 ID 和 API Key。</li><li>保存、测试并设为默认启用。</li><li>编辑时 API Key 留空表示不修改。</li></ol>
        <div class="callout warning"><strong>AI 的边界</strong>OR-Tools 负责硬约束和路线求解；AI 负责解释与风险提示。标准基线中 AI 不改变路线。</div>
        <h3>高德地图</h3>{amap}<ol><li>进入“系统设置 → 地图服务”。</li><li>填写 Web 端 Key 与配套安全密钥。</li><li>保存、测试并设为默认启用。</li></ol>
        <div class="callout"><strong>配置会保留</strong>停止、重启和一键恢复都会保留 AI Key 与高德配置。</div>
      </section>

      <section id="reset"><div class="section-title"><span class="num">10</span><div><h2>一键恢复标准状态</h2><p class="lead">操作错、数据改乱或事件残留时回到标准起点</p></div></div>
        <ol><li>关闭正在操作的平台页面。</li><li>双击“一键恢复标准演示数据.bat”。</li><li>脚本先备份 PostgreSQL 数据库，再恢复业务状态。</li><li>等待“标准演示数据已经恢复”，重新登录。</li></ol>
        <div class="table-wrap"><table><thead><tr><th>范围</th><th>内容</th></tr></thead><tbody>
          <tr><td>恢复</td><td>18 个已校准节点、12 个订单、5 辆车、标准账号、初始调度和待处置事件。</td></tr>
          <tr><td>清理</td><td>审批、执行、历史运行和临时事件记录。</td></tr>
          <tr><td>保留</td><td>AI 服务连接、高德地图连接、数据质量规则。</td></tr>
          <tr><td>备份</td><td>项目目录下 <code>backups</code> 文件夹。</td></tr>
        </tbody></table></div>
      </section>

      <section id="script"><div class="section-title"><span class="num">11</span><div><h2>8 分钟讲解顺序</h2><p class="lead">按业务问题 → 求解 → 事件 → 执行说明</p></div></div>
        <div class="timeline"><div class="time-row"><b>0:00—1:00</b><span>登录与运营总览：说明多订单、多车型、冷链和时间窗约束。</span></div>
        <div class="time-row"><b>1:00—3:30</b><span>生成调度：查看 3 条路线、地图顺序和优化指标。</span></div>
        <div class="time-row"><b>3:30—5:30</b><span>动态事件：启动固定故障处置，说明冻结任务和增量重算。</span></div>
        <div class="time-row"><b>5:30—6:40</b><span>执行中心：说明管理员审批、驾驶员接单和状态回传。</span></div>
        <div class="time-row"><b>6:40—7:30</b><span>算法边界：OR-Tools 保证可行性，AI 负责解释和风险提示。</span></div>
        <div class="time-row"><b>7:30—8:00</b><span>总结：路线可计算、过程可执行、结果可追溯，可一键恢复。</span></div></div>
        <div class="callout"><strong>一句话概括</strong>祁智运把县域订单、运力和突发事件统一成可计算的调度问题，再把结果转成地图路线、审批任务和驾驶员执行闭环。</div>
      </section>

      <section id="faq"><div class="section-title"><span class="num">12</span><div><h2>常见问题与快速排查</h2><p class="lead">先确认服务和账号，再检查配置与业务状态</p></div></div>
        <div class="table-wrap"><table><thead><tr><th>问题</th><th>处理方法</th></tr></thead><tbody>
          <tr><td>页面打不开</td><td>双击“检查平台状态.bat”，确认 Docker Desktop 已运行。</td></tr>
          <tr><td>登录失败</td><td>确认大小写和感叹号；锁定后等待 15 分钟。</td></tr>
          <tr><td>地图空白</td><td>检查地图服务的默认连接和测试状态，然后刷新。</td></tr>
          <tr><td>AI 401</td><td>API Key 无效或 Base URL 不匹配；编辑连接后重新测试。</td></tr>
          <tr><td>结果不同</td><td>先一键恢复，再使用标准运营基线生成方案。</td></tr>
          <tr><td>故障红点仍在</td><td>确认处置进度 100%，刷新；仍异常则一键恢复。</td></tr>
          <tr><td>驾驶员无全局地图</td><td>正常权限设计；驾驶员仅访问本人任务。</td></tr>
        </tbody></table></div>
      </section>
    </div>
    <footer>祁智运县域物流智能决策平台 · 图文使用手册 · 2026.07</footer>
  </main>
</div>
<a class="top" href="#top" aria-label="返回顶部">↑</a>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screens", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build(args.screens.resolve()), encoding="utf-8")


if __name__ == "__main__":
    main()
