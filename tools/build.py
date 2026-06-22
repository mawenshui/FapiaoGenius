"""构建智票通 - 便携版 + 安装版"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import zipfile

PROJECT_DIR = Path(__file__).parent.parent
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"
VERSION = "1.0.0"
APP_NAME = "智票通"
EXE_NAME = "ai_fapiao.exe"

# 需要打包的数据文件
DATAS = [
    ("config/builtin_rules/*.json", "config/builtin_rules"),
    ("resources/styles/*.qss", "resources/styles"),
]


def clean_build():
    """清理构建目录"""
    print("[1/6] 清理旧构建...")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)


def build_exe():
    """使用 PyInstaller 构建可执行文件"""
    print("[2/6] 构建可执行文件...")
    
    datas_args = []
    for src, dest in DATAS:
        datas_args.extend(["--add-data", f"{src};{dest}"])
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "ai_fapiao",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--paths", str(PROJECT_DIR),
        *datas_args,
        str(PROJECT_DIR / "main.py")
    ]
    
    result = subprocess.run(cmd, cwd=PROJECT_DIR)
    if result.returncode != 0:
        print("❌ PyInstaller 构建失败")
        sys.exit(1)
    
    print("✅ 可执行文件构建成功")


def copy_builtin_rules():
    """将最新内置规则复制到构建产物目录"""
    print("[3/6] 复制内置规则...")
    
    # 便携版目录
    portable_rules_dir = DIST_DIR / "ai_fapiao" / "config" / "builtin_rules"
    portable_rules_dir.mkdir(parents=True, exist_ok=True)
    
    src_rules = PROJECT_DIR / "config" / "builtin_rules"
    for rule_file in src_rules.glob("*.json"):
        shutil.copy2(rule_file, portable_rules_dir / rule_file.name)
        print(f"  ✅ 复制: {rule_file.name}")


def create_portable_zip():
    """创建便携版 ZIP"""
    print("[4/6] 创建便携版 ZIP...")
    
    zip_name = f"{APP_NAME}_v{VERSION}_Portable.zip"
    zip_path = DIST_DIR / zip_name
    
    # 便携版目录
    portable_dir = DIST_DIR / "ai_fapiao"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(portable_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(DIST_DIR)
                zf.write(file_path, arcname)
    
    print(f"✅ 便携版 ZIP 已创建: {zip_name}")


def build_msi():
    """使用 cx_Freeze 构建 MSI 安装包"""
    print("[5/6] 构建 MSI 安装包...")
    
    try:
        import cx_Freeze
    except ImportError:
        print("⚠️  cx_Freeze 未安装，跳过 MSI 构建")
        print("   安装命令: pip install cx_Freeze")
        return
    
    # 创建 cx_Freeze setup 脚本
    setup_content = f'''from cx_Freeze import setup, Executable
import sys

build_exe_options = {{
    "packages": ["PyQt5", "pdfplumber", "openpyxl", "cryptography"],
    "include_files": [
        ("config/builtin_rules", "config/builtin_rules"),
        ("resources/styles", "resources/styles"),
    ],
}}

base = "gui" if sys.platform == "win32" else None

setup(
    name="{APP_NAME}",
    version="{VERSION}",
    description="AI 智能发票识别管理系统",
    options={{"build_exe": build_exe_options}},
    executables=[Executable("main.py", base=base, target_name="{EXE_NAME}")],
)
'''
    
    setup_path = BUILD_DIR / "setup_cx.py"
    BUILD_DIR.mkdir(exist_ok=True)
    with open(setup_path, 'w', encoding='utf-8') as f:
        f.write(setup_content)
    
    # 运行 cx_Freeze bdist_msi
    cmd = [sys.executable, str(setup_path), "build_exe", "bdist_msi"]
    result = subprocess.run(cmd, cwd=PROJECT_DIR)
    
    if result.returncode != 0:
        print("❌ cx_Freeze MSI 构建失败")
        return
    
    # 移动 MSI 到 dist 目录
    for msi_file in PROJECT_DIR.glob("*.msi"):
        msi_dest = DIST_DIR / msi_file.name
        shutil.move(str(msi_file), str(msi_dest))
        print(f"✅ MSI 安装包已创建: {msi_file.name}")
        break
    else:
        print("⚠️  未找到生成的 MSI 文件")


def verify():
    """验证构建产物"""
    print("[6/6] 验证构建产物...")
    
    # 检查便携版 ZIP
    zip_files = list(DIST_DIR.glob("*Portable.zip"))
    if zip_files:
        print(f"✅ 便携版: {zip_files[0].name} ({zip_files[0].stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        print("❌ 便携版 ZIP 未找到")
    
    # 检查 MSI
    msi_files = list(DIST_DIR.glob("*.msi"))
    if msi_files:
        print(f"✅ 安装版: {msi_files[0].name} ({msi_files[0].stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        print("⚠️  MSI 未生成（WiX 未安装）")
    
    # 检查内置规则
    portable_rules = DIST_DIR / "ai_fapiao" / "config" / "builtin_rules"
    if portable_rules.exists():
        rule_count = len(list(portable_rules.glob("*.json")))
        print(f"✅ 内置规则: {rule_count} 个文件")
        for rule_file in portable_rules.glob("*.json"):
            print(f"   - {rule_file.name}")
    else:
        print("❌ 内置规则目录未找到")


def main():
    print(f"🚀 开始构建 {APP_NAME} v{VERSION}")
    print("=" * 60)
    
    clean_build()
    build_exe()
    copy_builtin_rules()
    create_portable_zip()
    build_msi()
    verify()
    
    print("=" * 60)
    print("🎉 构建完成!")


if __name__ == "__main__":
    main()
