import streamlit as st
import requests
from urllib.parse import urlparse, parse_qs

# --- 核心逻辑函数 ---

def check_ctv_validity(token):
    """
    测试模板链接并验证 CloudFront 状态
    逻辑判定：
    1. True: Status 200 & x-cache contains 'Miss from cloudfront'
    2. False: Status 400
    3. False (200+Error from cloud front): Status 200 & x-cache DOES NOT contain 'Miss from cloudfront'
    """
    test_url = f"https://impressions.onelink.me/{token}?pid=googleadwords_int&af_siteid=128904821&af_ip=1.100.0.116&af_ua=Tubi%2B-%2BFree%2BMovies%2B%26%2BTV%2F3.4.2%2B%28Roku%2B14.1.4%3B%2Ben_US%3B%2B75R635%3B%2BBuild%2F7708%29&clickid=e50a5314-d59c-4b82-a290-fe98cdc1d9ab&af_xplatform=true&af_xplatform_vt_lookback=72h&af_viewthrough_lookback=24h"
    
    # 使用 GET 请求并模拟浏览器 Header，防止 405 或被 WAF 拦截
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }
    
    try:
        # 发送请求
        response = requests.get(test_url, headers=headers, timeout=12)
        status_code = response.status_code
        # 获取 CloudFront 缓存状态 (忽略大小写)
        x_cache = response.headers.get('x-cache', '') or response.headers.get('X-Cache', '')

        if status_code == 200:
            if "Miss from cloudfront" in x_cache:
                return "True", "✅ 验证通过：CloudFront 未命中 (Miss)，链路配置正确。"
            else:
                return "False (200+Error from cloud front)", f"⚠️ 异常：返回 200 但缓存状态为 '{x_cache}'，未触发 Miss。"
        elif status_code == 400:
            return "False", "❌ 验证失败：返回 400 Bad Request，请检查模板参数。"
        else:
            return f"False (Status: {status_code})", f"❌ 收到非预期状态码: {status_code}"
            
    except Exception as e:
        return "Error", f"🚫 网络连接失败: {str(e)}"

def parse_af_link(url):
    """拆解链接结构"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    path_parts = parsed_url.path.strip('/').split('/')
    params = {k: v[0] for k, v in parse_qs(parsed_url.query).items()}
    
    # 1. Link Category
    if "onelink.me" in domain:
        category = "Onelink"
    elif "appsflyer.com" in domain:
        category = "Normal"
    else:
        category = "Unknown"

    # 2. Link Type & Token
    link_type = "Unknown"
    token = path_parts[0] if path_parts else "N/A"
    
    # CTV 判定优先级最高
    if "impressions" in domain and params.get("af_xplatform") == "true":
        link_type = "CTV"
    # VTA 判定
    elif "impressions" in domain or "impression" in domain:
        link_type = "VTA"
    # CTA 判定
    elif "app.appsflyer.com" in domain or ("onelink.me" in domain and "impressions" not in domain):
        link_type = "CTA"
        
    return category, link_type, token, params

# --- Streamlit UI 界面 ---

st.set_page_config(page_title="AF Link Parser Pro", layout="wide")

st.title("🔗 AppsFlyer 链接结构拆解工具")
st.markdown("输入原始追踪链接，自动识别归因类型、验证 CloudFront 状态并拆解所有参数。")

# 输入区
url_input = st.text_area("请粘贴广告链接:", placeholder="https://impressions.onelink.me/...", height=100)

# 开始解析按钮
if st.button("开始解析 🚀"):
    if url_input:
        with st.spinner('正在深度解析中...'):
            url_clean = url_input.strip()
            category, link_type, token, params = parse_af_link(url_clean)
            
            # 只有 Onelink 且包含 Token 时进行 CTV 验证
            ctv_status, ctv_msg = "N/A", "无需验证"
            if category == "Onelink" and token != "N/A":
                ctv_status, ctv_msg = check_ctv_validity(token)

            # 第一排：核心指标展示
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Link Category", category)
            with col2:
                st.metric("Link Type", link_type)
            with col3:
                st.metric("Onelink Token", token)
            with col4:
                # 动态设置指标颜色
                is_true = "True" in ctv_status and "False" not in ctv_status
                st.metric("Is Valid CTV", ctv_status, 
                          delta="Valid" if is_true else "Check Failed", 
                          delta_color="normal" if is_true else "inverse")

            # 验证详情说明
            st.info(f"**CTV 验证详情:** {ctv_msg}")

            st.divider()
            
            # 第二排：参数明细表格
            st.subheader("🛠 参数明细 (Query Parameters)")
            if params:
                param_list = [{"Parameter": k, "Value": v} for k, v in params.items()]
                st.table(param_list)
            else:
                st.warning("未检测到 Query 参数。")
    else:
        st.error("请先粘贴需要解析的链接！")

# 侧边栏说明
with st.sidebar:
    st.header("关于验证逻辑")
    st.markdown("""
    - **True**: 200 OK + `Miss from cloudfront`
    - **False**: 400 Bad Request
    - **False (200+Error)**: 200 OK 但 `X-Cache` 为 Hit 或其他。
    """)
    st.caption("提示：由于网络环境影响，建议在海外环境运行以获得最准确的 CloudFront 状态。")