#!/usr/bin/env python3
"""Orchestrate the OpenRCT2 sprite reskin pipeline.

Chains: batch -> generate -> parse for a sprite directory or workspace.

Workspace mode (from init-reskin-object-workspace.sh):
    python3 reskin.py --workspace ./reskin-workbench/my-object --style "fantasy style"
    python3 reskin.py --workspace ./reskin-workbench/my-object --step parse

Standalone mode (any PNG directory):
    python3 reskin.py --sprites-dir ./sprites --style "pixel art" --through generate
    python3 reskin.py --sprites-dir ./sprites --step parse

Steps: batch -> generate -> parse
"""

import os
import sys
import argparse

# Allow imports from this directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from categories import CATEGORIES
from batch_sprites import batch_sprites
from generate_restyled import generate_all
from parse_restyled import parse_restyled

STEPS = ["batch", "generate", "parse"]


def resolve_dirs(args):
    """Resolve sprites_dir, batch_dir, restyled_dir from args.

    Returns (sprites_dir, batch_dir, restyled_dir, output_dir).
    """
    if args.workspace:
        base = args.workspace
        sprites_dir = os.path.join(base, "sprites")
        batch_dir = os.path.join(base, "batches")
        restyled_dir = os.path.join(base, "restyled")
        output_dir = sprites_dir  # overwrite originals in workspace
        if not os.path.isdir(sprites_dir):
            print(f"ERROR: Workspace sprites dir not found: {sprites_dir}")
            sys.exit(1)
    elif args.sprites_dir:
        sprites_dir = args.sprites_dir
        parent = os.path.dirname(sprites_dir.rstrip("/"))
        batch_dir = os.path.join(parent, "batches")
        restyled_dir = os.path.join(parent, "restyled")
        output_dir = args.output_dir or sprites_dir
    else:
        print("ERROR: Provide --workspace or --sprites-dir")
        sys.exit(1)

    # Allow explicit overrides
    batch_dir = args.batch_dir or batch_dir
    restyled_dir = args.restyled_dir or restyled_dir
    output_dir = args.output_dir or output_dir

    return sprites_dir, batch_dir, restyled_dir, output_dir


def resolve_style(args):
    """Get style prompt from args or category."""
    if args.style:
        return args.style
    if args.category and args.category in CATEGORIES:
        return CATEGORIES[args.category]["style_prompt"]
    return ""


def resolve_tiling(args):
    """Get tiling flag from args or category."""
    if args.tiling:
        return True
    if args.no_tiling:
        return False
    if args.category and args.category in CATEGORIES:
        return CATEGORIES[args.category].get("tiling", False)
    return None  # let manifest decide


def resolve_description_hint(args):
    """Get description hint from args or category."""
    if args.description_hint:
        return args.description_hint
    if args.category and args.category in CATEGORIES:
        return CATEGORIES[args.category].get("description_hint", "game sprite")
    return "game sprite"


def run_step(step, sprites_dir, batch_dir, restyled_dir, output_dir, args):
    """Run one pipeline step."""
    manifest_path = os.path.join(batch_dir, "manifest.json")

    if step == "batch":
        print("\n--- Batch ---")
        style = resolve_style(args)
        tiling = resolve_tiling(args)
        hint = resolve_description_hint(args)
        batch_sprites(
            sprites_dir=sprites_dir,
            batch_dir=batch_dir,
            style_prompt=style,
            description_hint=hint,
            tiling=tiling if tiling is not None else False,
        )

    elif step == "generate":
        print("\n--- Generate ---")
        if not os.path.exists(manifest_path):
            print(f"ERROR: {manifest_path} not found. Run batch step first.")
            return False

        if not os.environ.get("FAL_KEY"):
            print("ERROR: FAL_KEY environment variable not set")
            return False

        style = resolve_style(args)
        descriptions_dir = args.descriptions_dir
        generate_all(
            manifest_path=manifest_path,
            restyled_dir=restyled_dir,
            style=style or None,
            descriptions_dir=descriptions_dir,
            skip_existing=args.skip_existing,
        )

    elif step == "parse":
        print("\n--- Parse ---")
        if not os.path.exists(manifest_path):
            print(f"ERROR: {manifest_path} not found. Run batch step first.")
            return False

        tiling = resolve_tiling(args)
        parse_restyled(
            manifest_path=manifest_path,
            sprites_dir=sprites_dir,
            restyled_dir=restyled_dir,
            output_dir=output_dir,
            tiling=tiling,
            dry_run=args.dry_run,
        )

    return True


def main():
    parser = argparse.ArgumentParser(
        description="OpenRCT2 AI sprite reskin pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Workspace mode
  python3 reskin.py --workspace ./reskin-workbench/my-object \\
      --style "Cartoony fantasy, bold outlines" --through generate
  python3 reskin.py --workspace ./reskin-workbench/my-object --step parse

  # Standalone mode
  python3 reskin.py --sprites-dir ./sprites --style "pixel art" --tiling

  # Using a category preset
  python3 reskin.py --sprites-dir ./sprites --category scenery_small
""",
    )

    # Input source (one required)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--workspace", help="Reskin workspace dir "
                        "(from init-reskin-object-workspace.sh)")
    source.add_argument("--sprites-dir", help="Directory of sprite PNGs")

    # Style
    parser.add_argument("--style", default=None, help="Style prompt for AI")
    parser.add_argument("--category", default=None,
                        choices=list(CATEGORIES.keys()),
                        help="Use a category preset for style/tiling/hints")
    parser.add_argument("--description-hint", default=None,
                        help="Hint for per-cell descriptions")
    parser.add_argument("--descriptions-dir", default=None,
                        help="Dir with per-batch description JSON files")

    # Tiling
    parser.add_argument("--tiling", action="store_true",
                        help="Enable tile edge blending")
    parser.add_argument("--no-tiling", action="store_true",
                        help="Disable tile edge blending")

    # Step control
    parser.add_argument("--step", choices=STEPS,
                        help="Run only this step")
    parser.add_argument("--through", choices=STEPS,
                        help="Run all steps through this one")

    # Flags
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse step: validate only")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Generate step: skip existing outputs")

    # Path overrides
    parser.add_argument("--batch-dir", default=None)
    parser.add_argument("--restyled-dir", default=None)
    parser.add_argument("--output-dir", default=None)

    # Info
    parser.add_argument("--list-categories", action="store_true",
                        help="List available category presets and exit")

    args = parser.parse_args()

    if args.list_categories:
        print("Available categories:")
        for name, cfg in CATEGORIES.items():
            tiling = "tiling" if cfg.get("tiling") else "no-tiling"
            print(f"  {name:20s} [{tiling}]")
            print(f"    {cfg['style_prompt'][:80]}...")
        return

    if not args.workspace and not args.sprites_dir:
        parser.print_help()
        return

    sprites_dir, batch_dir, restyled_dir, output_dir = resolve_dirs(args)

    print(f"Sprites:  {sprites_dir}")
    print(f"Batches:  {batch_dir}")
    print(f"Restyled: {restyled_dir}")
    print(f"Output:   {output_dir}")

    if args.step:
        steps = [args.step]
    elif args.through:
        idx = STEPS.index(args.through)
        steps = STEPS[:idx + 1]
    else:
        steps = STEPS

    for step in steps:
        ok = run_step(step, sprites_dir, batch_dir, restyled_dir, output_dir, args)
        if not ok:
            print(f"\nStep '{step}' failed. Stopping.")
            sys.exit(1)

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
