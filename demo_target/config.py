# ⚠️ 演示用假密钥（非真实凭据）—— 故意硬编码，供 github-secret-auditor 巡检演示
MYAPP_API_KEY = "live_FAKE_demo_0123456789abcdef_DO_NOT_USE"
DATABASE_URL = "postgres://demo_user:FAKE_pw_demo_2026@db.example.invalid:5432/appdb"


def get_client():
    # 直接用了上面硬编码的凭据 —— 正是要被巡检并修复的反模式
    return {"api_key": MYAPP_API_KEY, "db": DATABASE_URL}
