#!/usr/bin/env python3
"""
Generate ArgoCD Application manifests for GitHub Actions workflows.
Uses ruamel.yaml + post-processing for precise 2-space list indentation.
"""

import argparse
import os
import re
import sys
from io import StringIO
from ruamel.yaml import YAML


#--------------------------------
# Helpers
#--------------------------------

def is_chart_version(version: str) -> bool:
    """Return True if targetRevision looks like a semver chart version (e.g. 0.0.0)."""
    return bool(re.match(r"^\d+\.\d+\.\d+", version))


def build_manifest_git(args) -> dict:
    """Build ArgoCD Application manifest for Git repo source."""
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "finalizers": ["resources-finalizer.argocd.argoproj.io"],
            "name": f"{args.chart_name}-{args.environment}",
            "namespace": args.namespace
        },
        "spec": {
            "ignoreDifferences": [
                {
                    "group": "apps",
                    "kind": "Deployment",
                    "jsonPointers": ["/spec/replicas"]
                },
                {
                    "group": "apps",
                    "kind": "StatefulSet",
                    "jsonPointers": ["/spec/replicas"]
                }
            ],
            "project": args.project,
            "source": {
                "repoURL": f"https://github.com/industrial-solutions/{args.repo_name}.git",
                "targetRevision": args.target_revision,
                "path": f"charts/{args.chart_name}"
            },
            "destination": {
                "server": args.destination_server,
                "namespace": args.destination_namespace
            },
            "syncPolicy": {
                "automated": {
                    "prune": True,
                    "selfHeal": True,
                }
            },
        },
    }


def build_manifest_helm(args) -> dict:
    """Build ArgoCD Application manifest for Helm/OCI chart source."""
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "finalizers": ["resources-finalizer.argocd.argoproj.io"],
            "name": f"{args.chart_name}-{args.environment}",
            "namespace": args.namespace
        },
        "spec": {
            "ignoreDifferences": [
                {
                    "group": "apps",
                    "kind": "Deployment",
                    "jsonPointers": ["/spec/replicas"]
                },
                {
                    "group": "apps",
                    "kind": "StatefulSet",
                    "jsonPointers": ["/spec/replicas"]
                }
            ],
            "project": args.project,
            "source": {
                "repoURL": "ghcr.io/industrial-solutions",
                "targetRevision": args.target_revision,
                "chart": args.chart_name,
            },
            "destination": {
                "server": args.destination_server,
                "namespace": args.destination_namespace
            },
            "syncPolicy": {
                "automated": {
                    "prune": True,
                    "selfHeal": True,
                }
            },
        },
    }


def fix_yaml_indentation(content: str) -> str:
    """
    Post-process YAML to enforce exact 2-space indentation for list items.
    
    Desired format:
      parent_key:
      - item1
        nested_key:
        - nested_item
    """
    lines = content.split('\n')
    result = []
    
    for line in lines:
        stripped = line.lstrip()
        
        # Skip empty lines or comment-only lines
        if not stripped or stripped.startswith('#'):
            result.append(line)
            continue
        
        # Count leading spaces to determine current indentation level
        current_indent = len(line) - len(stripped)
        
        # If this is a list item (starts with '- ')
        if stripped.startswith('- '):
            # We want list dashes to be at the same indentation as their sibling keys
            # So if parent key is at N spaces, dash should also be at N spaces
            # Content inside the list item should be at N+2 spaces
            
            # Extract the content after the dash
            item_content = stripped[2:]  # Remove '- '
            
            # Keep the dash at current_indent (same as sibling keys)
            # But content after dash should be indented 2 more spaces
            if item_content.startswith(' '):
                # Already has some indentation, normalize to 2 spaces after dash
                item_content = item_content.lstrip()
            
            # Rebuild line: [indent]- [content with 2-space nested indent]
            result.append(' ' * current_indent + '- ' + item_content)
        else:
            # For non-list lines, ensure consistent 2-space mapping indentation
            # (ruamel.yaml usually handles this well, but we normalize just in case)
            key_match = re.match(r'^(\w+):', stripped)
            if key_match and current_indent > 0:
                # Ensure indentation is a multiple of 2
                normalized_indent = (current_indent // 2) * 2
                result.append(' ' * normalized_indent + stripped)
            else:
                result.append(line)
    
    return '\n'.join(result)


def write_manifest(file_path: str, manifest: dict, dry_run: bool = False) -> None:
    """Write the YAML manifest with precise 2-space list indentation."""
    
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.sort_keys = False
    
    # Base indentation settings
    yaml.indent(mapping=2, sequence=4, offset=2)
    
    # Write to string first
    stream = StringIO()
    yaml.dump(manifest, stream)
    content = stream.getvalue()
    
    # Post-process to fix list indentation exactly as desired
    content = fix_yaml_indentation(content)
    
    if dry_run:
        print(f"\n[DRY-RUN] Would write to: {file_path}")
        print("_" * 60)
        print(content)
        print("_" * 60)
        return
    
    # Ensure output directory exists
    output_dir = os.path.dirname(file_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Manifest written to: {file_path}")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate ArgoCD Application manifests for GitHub Actions workflows"
    )
    
    # Required arguments
    parser.add_argument("--chart-name", required=True, help="Name of the Helm chart")
    parser.add_argument("--environment", required=True, help="Target environment (e.g., dev, staging, prod)")
    parser.add_argument("--namespace", required=True, help="Kubernetes namespace for the ArgoCD Application resource")
    parser.add_argument("--target-revision", required=True, help="Git branch/tag or Helm chart version")
    parser.add_argument("--destination-server", required=True, help="Kubernetes cluster server URL")
    parser.add_argument("--destination-namespace", required=True, help="Target namespace for deployed resources")
    parser.add_argument("--filename", required=True, help="Output YAML file path")
    
    # Source type selection
    parser.add_argument(
        "--source-type", 
        choices=["git", "helm"], 
        required=True, 
        help="Source type: 'git' for GitHub repo, 'helm' for OCI/Helm registry"
    )
    
    # Conditional arguments
    parser.add_argument("--repo-name", help="GitHub repo name (required when --source-type=git)")
    
    # Optional arguments
    parser.add_argument(
        "--project", 
        default="default", 
        help="ArgoCD project name (default: 'default')"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print manifest to stdout instead of writing file")
    
    args = parser.parse_args()
    
    # Validate conditional requirements
    if args.source_type == "git" and not args.repo_name:
        parser.error("--repo-name is required when --source-type=git")
    
    return args


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Select manifest builder based on source type
    if args.source_type == "git":
        manifest = build_manifest_git(args)
    elif args.source_type == "helm":
        manifest = build_manifest_helm(args)
    else:
        print(f"Error: Unknown source type '{args.source_type}'", file=sys.stderr)
        sys.exit(1)
    
    # Write or print the manifest
    write_manifest(args.filename, manifest, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
