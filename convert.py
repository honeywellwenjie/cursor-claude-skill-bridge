#!/usr/bin/env python3
"""
Cursor <-> Claude Code Skill Converter

Converts skill packages between Cursor and Claude Code (Codex) formats.

Both formats use SKILL.md with YAML frontmatter (name + description),
but differ in directory structure conventions and storage locations.

Key differences:
  - Claude Code: scripts/, references/, assets/ subdirectories recommended;
    loose scripts alongside SKILL.md are common.
  - Cursor: scripts/ subdirectory; reference.md / examples.md alongside SKILL.md;
    SKILL.md should be under 500 lines.

Usage:
  # Claude -> Cursor
  python convert.py claude2cursor ~/.claude/skills/my-skill -o ~/.cursor/skills/my-skill

  # Cursor -> Claude
  python convert.py cursor2claude ~/.cursor/skills/my-skill -o ~/.claude/skills/my-skill

  # Auto-detect direction
  python convert.py auto ~/.claude/skills/my-skill -o ./output/my-skill
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path


CLAUDE_SKILL_MARKERS = [".claude/skills", ".codex/skills"]
CURSOR_SKILL_MARKERS = [".cursor/skills"]

SCRIPT_EXTENSIONS = {".py", ".sh", ".bash", ".js", ".ts", ".rb", ".pl"}
REFERENCE_EXTENSIONS = {".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".csv"}
ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".pptx", ".xlsx", ".docx", ".pdf", ".ttf", ".otf", ".woff", ".woff2",
    ".html", ".css", ".zip", ".tar", ".gz",
}


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from SKILL.md content.

    Returns (metadata_dict, body_text).
    """
    if not content.startswith("---"):
        return {}, content

    end = content.find("---", 3)
    if end == -1:
        return {}, content

    frontmatter_text = content[3:end].strip()
    body = content[end + 3:].lstrip("\n")

    metadata = {}
    for line in frontmatter_text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key and value:
                metadata[key] = value
    return metadata, body


def build_frontmatter(metadata: dict) -> str:
    """Build YAML frontmatter string from metadata dict."""
    lines = ["---"]
    if "name" in metadata:
        lines.append(f"name: {metadata['name']}")
    if "description" in metadata:
        lines.append(f"description: {metadata['description']}")
    lines.append("---")
    return "\n".join(lines)


def classify_file(filepath: Path) -> str:
    """Classify a file into script / reference / asset category."""
    ext = filepath.suffix.lower()
    if ext in SCRIPT_EXTENSIONS:
        return "script"
    if ext in REFERENCE_EXTENSIONS:
        return "reference"
    if ext in ASSET_EXTENSIONS:
        return "asset"
    return "other"


def detect_direction(source: Path) -> str:
    """Auto-detect conversion direction based on source path."""
    source_str = str(source.resolve())
    for marker in CLAUDE_SKILL_MARKERS:
        if marker in source_str:
            return "claude2cursor"
    for marker in CURSOR_SKILL_MARKERS:
        if marker in source_str:
            return "cursor2claude"
    return ""


def collect_files(source: Path) -> dict[str, list[Path]]:
    """Collect and classify all files in the skill directory.

    Returns dict with keys: skill_md, scripts, references, assets, other.
    """
    result: dict[str, list[Path]] = {
        "skill_md": [],
        "scripts": [],
        "references": [],
        "assets": [],
        "other": [],
    }

    for item in sorted(source.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(source)
        rel_str = str(rel)

        # Skip hidden files
        if any(part.startswith(".") for part in rel.parts):
            continue

        if rel.name == "SKILL.md":
            result["skill_md"].append(item)
            continue

        # Already in organized subdirectory
        first_dir = rel.parts[0] if len(rel.parts) > 1 else ""
        if first_dir == "scripts":
            result["scripts"].append(item)
        elif first_dir in ("references", "reference"):
            result["references"].append(item)
        elif first_dir == "assets":
            result["assets"].append(item)
        else:
            category = classify_file(item)
            if category == "script":
                result["scripts"].append(item)
            elif category == "reference":
                result["references"].append(item)
            elif category == "asset":
                result["assets"].append(item)
            else:
                result["other"].append(item)

    return result


def update_references_in_body(body: str, path_mappings: dict[str, str]) -> str:
    """Update file references in SKILL.md body based on path mappings."""
    updated = body
    for old_path, new_path in sorted(path_mappings.items(), key=lambda x: -len(x[0])):
        if old_path != new_path:
            updated = updated.replace(old_path, new_path)
    return updated


def convert_claude_to_cursor(source: Path, output: Path, dry_run: bool = False) -> None:
    """Convert a Claude Code skill to Cursor format.

    Main changes:
    - Loose script files (.py, .sh, etc.) are moved into scripts/ subdirectory
    - references/ directory content stays as-is or becomes reference files alongside SKILL.md
    - assets/ content is moved into the skill directory
    - SKILL.md frontmatter is kept (only name + description)
    - Extra frontmatter fields (like metadata) are stripped
    """
    files = collect_files(source)

    if not files["skill_md"]:
        print(f"错误: 在 {source} 中未找到 SKILL.md 文件", file=sys.stderr)
        sys.exit(1)

    skill_md_path = files["skill_md"][0]
    content = skill_md_path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)

    # Cursor only uses name + description in frontmatter
    cursor_metadata = {}
    if "name" in metadata:
        cursor_metadata["name"] = metadata["name"]
    if "description" in metadata:
        cursor_metadata["description"] = metadata["description"]

    path_mappings: dict[str, str] = {}

    if dry_run:
        print(f"\n[预览] Claude -> Cursor 转换")
        print(f"  源目录: {source}")
        print(f"  输出目录: {output}")
        print(f"  Skill 名称: {cursor_metadata.get('name', 'N/A')}")
        print(f"  文件数量: {sum(len(v) for v in files.values())}")

    # Create output directory
    if not dry_run:
        output.mkdir(parents=True, exist_ok=True)

    # Process scripts: ensure they are in scripts/ subdirectory
    for script_path in files["scripts"]:
        rel = script_path.relative_to(source)
        first_dir = rel.parts[0] if len(rel.parts) > 1 else ""

        if first_dir == "scripts":
            # Already in scripts/, keep the same relative path
            new_rel = rel
        else:
            # Loose script, move to scripts/
            new_rel = Path("scripts") / rel
            path_mappings[str(rel)] = str(new_rel)

        dest = output / new_rel
        if dry_run:
            print(f"  [脚本] {rel} -> {new_rel}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(script_path, dest)

    # Process references: flatten into skill directory for Cursor
    for ref_path in files["references"]:
        rel = ref_path.relative_to(source)
        first_dir = rel.parts[0] if len(rel.parts) > 1 else ""

        if first_dir in ("references", "reference") and len(rel.parts) == 2:
            # Move from references/foo.md to foo.md (alongside SKILL.md)
            new_rel = Path(rel.parts[-1])
            path_mappings[str(rel)] = str(new_rel)
        else:
            new_rel = rel

        dest = output / new_rel
        if dry_run:
            print(f"  [参考] {rel} -> {new_rel}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ref_path, dest)

    # Process assets
    for asset_path in files["assets"]:
        rel = asset_path.relative_to(source)
        new_rel = rel  # keep as-is
        dest = output / new_rel
        if dry_run:
            print(f"  [资源] {rel} -> {new_rel}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset_path, dest)

    # Process other files
    for other_path in files["other"]:
        rel = other_path.relative_to(source)
        dest = output / rel
        if dry_run:
            print(f"  [其他] {rel}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(other_path, dest)

    # Update SKILL.md
    updated_body = update_references_in_body(body, path_mappings)
    new_content = build_frontmatter(cursor_metadata) + "\n" + updated_body

    if dry_run:
        print(f"\n  [SKILL.md] 前置数据字段: {list(cursor_metadata.keys())}")
        if path_mappings:
            print(f"  [SKILL.md] 路径更新: {len(path_mappings)} 处")
    else:
        (output / "SKILL.md").write_text(new_content, encoding="utf-8")

    if not dry_run:
        print(f"✓ 转换完成: Claude -> Cursor")
        print(f"  输出: {output}")


def convert_cursor_to_claude(source: Path, output: Path, dry_run: bool = False) -> None:
    """Convert a Cursor skill to Claude Code format.

    Main changes:
    - Reference .md files alongside SKILL.md are moved into references/ subdirectory
    - scripts/ content stays in scripts/
    - Loose scripts are moved to scripts/
    - SKILL.md frontmatter is kept (only name + description)
    """
    files = collect_files(source)

    if not files["skill_md"]:
        print(f"错误: 在 {source} 中未找到 SKILL.md 文件", file=sys.stderr)
        sys.exit(1)

    skill_md_path = files["skill_md"][0]
    content = skill_md_path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)

    claude_metadata = {}
    if "name" in metadata:
        claude_metadata["name"] = metadata["name"]
    if "description" in metadata:
        claude_metadata["description"] = metadata["description"]

    path_mappings: dict[str, str] = {}

    if dry_run:
        print(f"\n[预览] Cursor -> Claude 转换")
        print(f"  源目录: {source}")
        print(f"  输出目录: {output}")
        print(f"  Skill 名称: {claude_metadata.get('name', 'N/A')}")
        print(f"  文件数量: {sum(len(v) for v in files.values())}")

    if not dry_run:
        output.mkdir(parents=True, exist_ok=True)

    # Process scripts: ensure in scripts/
    for script_path in files["scripts"]:
        rel = script_path.relative_to(source)
        first_dir = rel.parts[0] if len(rel.parts) > 1 else ""

        if first_dir == "scripts":
            new_rel = rel
        else:
            new_rel = Path("scripts") / rel
            path_mappings[str(rel)] = str(new_rel)

        dest = output / new_rel
        if dry_run:
            print(f"  [脚本] {rel} -> {new_rel}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(script_path, dest)

    # Process references: move loose .md files into references/
    for ref_path in files["references"]:
        rel = ref_path.relative_to(source)
        first_dir = rel.parts[0] if len(rel.parts) > 1 else ""

        if first_dir in ("references", "reference"):
            new_rel = rel
        elif len(rel.parts) == 1 and rel.suffix.lower() == ".md":
            # Loose .md file alongside SKILL.md -> references/
            new_rel = Path("references") / rel
            path_mappings[str(rel)] = str(new_rel)
        else:
            new_rel = rel

        dest = output / new_rel
        if dry_run:
            print(f"  [参考] {rel} -> {new_rel}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ref_path, dest)

    # Process assets: move to assets/ if not already
    for asset_path in files["assets"]:
        rel = asset_path.relative_to(source)
        first_dir = rel.parts[0] if len(rel.parts) > 1 else ""

        if first_dir == "assets":
            new_rel = rel
        else:
            new_rel = Path("assets") / rel
            path_mappings[str(rel)] = str(new_rel)

        dest = output / new_rel
        if dry_run:
            print(f"  [资源] {rel} -> {new_rel}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset_path, dest)

    # Process other files
    for other_path in files["other"]:
        rel = other_path.relative_to(source)
        dest = output / rel
        if dry_run:
            print(f"  [其他] {rel}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(other_path, dest)

    # Update SKILL.md
    updated_body = update_references_in_body(body, path_mappings)
    new_content = build_frontmatter(claude_metadata) + "\n" + updated_body

    if dry_run:
        print(f"\n  [SKILL.md] 前置数据字段: {list(claude_metadata.keys())}")
        if path_mappings:
            print(f"  [SKILL.md] 路径更新: {len(path_mappings)} 处")
    else:
        (output / "SKILL.md").write_text(new_content, encoding="utf-8")

    if not dry_run:
        print(f"✓ 转换完成: Cursor -> Claude")
        print(f"  输出: {output}")


def main():
    parser = argparse.ArgumentParser(
        description="Cursor <-> Claude Code Skill 转换工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  # Claude skill -> Cursor skill
  python convert.py claude2cursor ~/.claude/skills/my-skill -o ~/.cursor/skills/my-skill

  # Cursor skill -> Claude skill
  python convert.py cursor2claude ~/.cursor/skills/my-skill -o ~/.claude/skills/my-skill

  # 自动检测方向
  python convert.py auto ~/.claude/skills/my-skill -o ./output/my-skill

  # 预览模式 (不写入文件)
  python convert.py claude2cursor ~/.claude/skills/my-skill -o ./out --dry-run
""",
    )

    parser.add_argument(
        "direction",
        choices=["claude2cursor", "cursor2claude", "auto"],
        help="转换方向: claude2cursor, cursor2claude, 或 auto (自动检测)",
    )
    parser.add_argument(
        "source",
        type=Path,
        help="源 skill 目录路径",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="输出目录路径 (默认: 当前目录下以 skill 名称命名)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式: 仅显示将执行的操作，不写入文件",
    )

    args = parser.parse_args()
    source = args.source.resolve()

    if not source.is_dir():
        print(f"错误: 源目录不存在: {source}", file=sys.stderr)
        sys.exit(1)

    skill_md = source / "SKILL.md"
    if not skill_md.is_file():
        print(f"错误: 未找到 SKILL.md: {skill_md}", file=sys.stderr)
        sys.exit(1)

    # Determine direction
    direction = args.direction
    if direction == "auto":
        direction = detect_direction(source)
        if not direction:
            print(
                "错误: 无法自动检测转换方向，请明确指定 claude2cursor 或 cursor2claude",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"自动检测方向: {direction}")

    # Determine output path
    output = args.output
    if output is None:
        skill_name = source.name
        output = Path.cwd() / skill_name
    output = output.resolve()

    if output.exists() and any(output.iterdir()):
        print(f"警告: 输出目录非空: {output}")
        response = input("是否继续? 已有文件可能被覆盖 (y/N): ")
        if response.lower() not in ("y", "yes"):
            print("已取消")
            sys.exit(0)

    # Execute conversion
    if direction == "claude2cursor":
        convert_claude_to_cursor(source, output, dry_run=args.dry_run)
    elif direction == "cursor2claude":
        convert_cursor_to_claude(source, output, dry_run=args.dry_run)
    else:
        print(f"错误: 未知方向 {direction}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
