#!/usr/bin/env bash
# Usage: ./scripts/slugify.sh "My New Architecture Title"
set -e
title="$*"
slug=$(printf "%s" "$title" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g;s/^-+|-+$//g')
echo "$slug"
