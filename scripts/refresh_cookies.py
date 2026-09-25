#!/usr/bin/env python3
"""
GLaDOS 双账号 Cookie 一键交互式/静默刷新与积分兑换工具 (方案 B)
Zero external dependencies (uses standard library urllib, json, subprocess)
"""

import sys
import os
import json
import urllib.request
import urllib.error
import subprocess
import argparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://glados.rocks",
    "Referer": "https://glados.rocks/login",
    "Content-Type": "application/json;charset=UTF-8"
}

DEFAULT_REPO = "yaping-pro/GLaDOS_checkin_auto"
DEFAULT_EMAILS = ["mayapingpro@gmail.com", "histevenma@gmail.com"]


def request_code(email: str) -> bool:
    """向指定邮箱发送登录 Access Code 验证码"""
    url = "https://glados.rocks/api/authorization"
    payload = json.dumps({"address": email.strip(), "site": "glados.network"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") == 0:
                print(f"✅ [{email}] 验证码邮件已发出（通道：{data.get('method', 'sendgrid')}）")
                return True
            else:
                print(f"❌ [{email}] 发送失败: {data}")
                return False
    except Exception as e:
        print(f"❌ [{email}] 请求异常: {e}")
        return False


def login_with_code(email: str, code: str) -> str:
    """使用邮箱和验证码登录，提取 koa:sess 和 koa:sess.sig Cookie"""
    url = "https://glados.rocks/api/login"
    payload = json.dumps({
        "method": "email",
        "site": "glados.network",
        "email": email.strip().lower(),
        "mailcode": code.strip()
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") != 0:
                print(f"❌ [{email}] 登录失败: {data.get('message', '未知错误')}")
                return ""
            
            # 从 Set-Cookie 响应头中抓取 session cookie (gld:sess 或 koa:sess)
            set_cookies = resp.headers.get_all("Set-Cookie") or []
            cookie_dict = {}
            for item in set_cookies:
                parts = item.split(";")[0].split("=", 1)
                if len(parts) == 2:
                    k, v = parts[0].strip(), parts[1].strip()
                    if k in ("gld:sess", "gld:sess.sig", "koa:sess", "koa:sess.sig"):
                        cookie_dict[k] = v
            
            if "gld:sess" in cookie_dict and "gld:sess.sig" in cookie_dict:
                cookie_str = f"gld:sess={cookie_dict['gld:sess']}; gld:sess.sig={cookie_dict['gld:sess.sig']}"
                print(f"🎉 [{email}] 登录成功！已成功提取最新 Cookie ({cookie_str[:30]}...)")
                return cookie_str
            elif "koa:sess" in cookie_dict and "koa:sess.sig" in cookie_dict:
                cookie_str = f"koa:sess={cookie_dict['koa:sess']}; koa:sess.sig={cookie_dict['koa:sess.sig']}"
                print(f"🎉 [{email}] 登录成功！已成功提取最新 Cookie ({cookie_str[:30]}...)")
                return cookie_str
            else:
                print(f"⚠️ [{email}] 登录成功但未提取到完整 Session Cookie: {set_cookies}")
                return ""
    except Exception as e:
        print(f"❌ [{email}] 登录异常: {e}")
        return ""


def get_account_status(cookie: str) -> dict:
    """获取账号的邮箱、积分和剩余服务天数"""
    headers = {**HEADERS, "Cookie": cookie}
    status = {"email": "", "points": 0, "leftDays": 0}
    
    # 1. 状态查询
    try:
        req = urllib.request.Request("https://glados.rocks/api/user/status", headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8")).get("data", {})
            status["email"] = data.get("email", "")
            status["leftDays"] = int(float(data.get("leftDays", 0)))
    except Exception as e:
        print(f"查询状态异常: {e}")

    # 2. 积分查询
    try:
        req = urllib.request.Request("https://glados.rocks/api/user/points", headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            status["points"] = int(float(data.get("points", 0)))
    except Exception as e:
        print(f"查询积分异常: {e}")
        
    return status


def exchange_points(cookie: str, plan_type: str = "plan200") -> bool:
    """兑换积分: plan100(100分=10天), plan200(200分=30天), plan500(500分=100天)"""
    url = "https://glados.rocks/api/user/exchange"
    payload = json.dumps({"planType": plan_type}).encode("utf-8")
    headers = {**HEADERS, "Cookie": cookie}
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") == 0:
                print(f"🎉 积分兑换成功 [{plan_type}]: {data.get('message', '兑换成功')} (当前结余: {data.get('points')} 分)")
                return True
            else:
                print(f"⚠️ 兑换失败: {data.get('message', '未知错误')}")
                return False
    except Exception as e:
        print(f"❌ 兑换异常: {e}")
        return False


def update_github_secret(combined_cookie: str, repo: str = DEFAULT_REPO) -> bool:
    """使用 gh CLI 将拼接好的 Cookie 写入 GitHub Secrets 并触发工作流"""
    try:
        cmd = ["gh", "secret", "set", "GLADOS_COOKIE", "--repo", repo]
        proc = subprocess.run(cmd, input=combined_cookie.encode("utf-8"), check=True, capture_output=True)
        print(f"✅ GitHub Secret [GLADOS_COOKIE] 更新成功！({repo})")
        
        # 触发运行测试
        run_cmd = ["gh", "workflow", "run", "runGladosAction.yml", "--repo", repo]
        subprocess.run(run_cmd, check=True, capture_output=True)
        print("🚀 已自动触发 GitHub Actions 每日签到工作流进行验证！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ GitHub 操作失败: {e.stderr.decode('utf-8')}")
        return False


def main():
    parser = argparse.ArgumentParser(description="GLaDOS 自动刷新 Cookie 与积分兑换 (方案 B)")
    parser.add_argument("--send-only", action="store_true", help="仅触发向预设邮箱发送 Access Code")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub 仓库路径")
    parser.add_argument("--account1-code", help="账号1 (mayapingpro) 的验证码")
    parser.add_argument("--account2-code", help="账号2 (histevenma) 的验证码")
    parser.add_argument("--auto-exchange", action="store_true", default=True, help="若积分充足且天数<=7则自动兑换")
    args = parser.parse_args()

    if args.send_only:
        print(">>> 正在向双账号发送 Access Code...")
        for em in DEFAULT_EMAILS:
            request_code(em)
        print(">>> 发送完成，请查收邮件并提供 6 位验证码。")
        return

    # 交互式或命令行参数获取验证码
    code1 = args.account1_code
    code2 = args.account2_code

    if not code1 or not code2:
        print("=== GLaDOS 方案 B：双账号 Cookie 刷新与自动续期 ===")
        print("如果尚未收到验证码，请按 Ctrl+C 退出后运行 `python3 refresh_cookies.py --send-only`。")
        if not code1:
            code1 = input(f"请输入 [{DEFAULT_EMAILS[0]}] 邮箱收到的 6 位验证码: ").strip()
        if not code2:
            code2 = input(f"请输入 [{DEFAULT_EMAILS[1]}] 邮箱收到的 6 位验证码: ").strip()

    if not code1 or not code2:
        print("❌ 验证码不完整，已终止操作。")
        sys.exit(1)

    # 1. 登录账号 1 (mayapingpro)
    print(f"\n>>> [1/2] 正在登录账号 1: {DEFAULT_EMAILS[0]}...")
    ck1 = login_with_code(DEFAULT_EMAILS[0], code1)
    if not ck1:
        print("❌ 账号 1 登录失败，终止后续流程。")
        sys.exit(1)

    status1 = get_account_status(ck1)
    print(f"📊 账号 1 状态: 剩余 {status1['leftDays']} 天 | 积分: {status1['points']} 分")

    # 紧急兑换：若积分 >= 200 且天数 <= 7，执行 200 积分兑换
    if status1['points'] >= 200:
        print("⚡ 检测到账号 1 积分达标，正在执行【200 积分 = 30 天】兑换...")
        if exchange_points(ck1, "plan200"):
            new_status1 = get_account_status(ck1)
            print(f"📊 兑换后最新状态: 剩余 {new_status1['leftDays']} 天 | 结余积分: {new_status1['points']} 分")

    # 2. 登录账号 2 (histevenma)
    print(f"\n>>> [2/2] 正在登录账号 2: {DEFAULT_EMAILS[1]}...")
    ck2 = login_with_code(DEFAULT_EMAILS[1], code2)
    if not ck2:
        print("❌ 账号 2 登录失败，终止后续流程。")
        sys.exit(1)

    status2 = get_account_status(ck2)
    print(f"📊 账号 2 状态: 剩余 {status2['leftDays']} 天 | 积分: {status2['points']} 分")

    # 3. 拼接 Cookie 并更新 GitHub Secrets
    print("\n>>> [3/3] 正在拼接双 Cookie 并写入 GitHub Secrets...")
    combined = f"{ck1}&{ck2}"
    update_github_secret(combined, repo=args.repo)
    print("\n🎉 全部操作圆满完成！")


if __name__ == "__main__":
    main()
