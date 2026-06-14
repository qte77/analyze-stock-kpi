#!/bin/bash
#
# World clock (opt-in)
# --------------------
# Local time is always shown. To append additional zones, configure either:
#
#   (1) CC_WORLD_CLOCK env var — set in your shell rc; persistent across
#       sessions. Requires CC restart to change (env is fixed at launch).
#
#   (2) ~/.claude/world-clock file — single line of comma-separated zones.
#       Live toggle: edit/delete the file and the next prompt render picks
#       it up, no CC restart needed. Use when you want to flip clocks on/off
#       inside an active session.
#
# Precedence: env var wins; file is the fallback. Unset env + missing/empty
# file = off (default).
#
# Zones render in the order you list them. Suggested convention:
# order east-to-west (sunrise order) so time decreases left-to-right.
#
# Each entry is either a bare IANA zone (label defaults to the city, e.g.
# "Europe/Paris" → "Paris") or "Zone=Label" to override the rendered label
# (e.g. "America/New_York=NYC" → "NYC"). Mix and match freely.
#
# Suggested default (env-var form, copy to your shell rc):
#   export CC_WORLD_CLOCK="Asia/Tokyo,Europe/Paris,Europe/London,UTC,America/New_York,America/Los_Angeles"
#
# Short-label variant (terser statusline):
#   export CC_WORLD_CLOCK="Asia/Tokyo=TYO,Europe/Paris=PAR,Europe/London=LDN,UTC,America/New_York=NYC,America/Los_Angeles=LA"
#
# Live-toggle form:
#   echo "Asia/Tokyo,Europe/Paris,Europe/London,UTC,America/New_York,America/Los_Angeles" > ~/.claude/world-clock
#   rm ~/.claude/world-clock                                                                # turn off
#
# Other examples:
#   export CC_WORLD_CLOCK="Asia/Tokyo,Asia/Singapore,UTC"
#
# Use IANA Region/City names (system tzdata under /usr/share/zoneinfo).
# DST is handled automatically. Invalid zones render as "?<name>" so typos
# are visible at a glance. On Alpine, install tzdata first: apk add tzdata.
#
# When set, world-clock zones render on their own line below the main
# statusline. If your local zone is in the list it will appear twice —
# omit it from CC_WORLD_CLOCK to avoid duplication.
#
# Curated shortlist (full list: find /usr/share/zoneinfo -type f):
#   UTC anchor : UTC
#   Americas   : America/Los_Angeles America/Denver America/Chicago
#                America/New_York America/Toronto America/Mexico_City
#                America/Sao_Paulo America/Argentina/Buenos_Aires
#   Europe     : Europe/London Europe/Dublin Europe/Lisbon Europe/Paris
#                Europe/Berlin Europe/Madrid Europe/Rome Europe/Amsterdam
#                Europe/Zurich Europe/Stockholm Europe/Warsaw Europe/Athens
#                Europe/Istanbul Europe/Moscow
#   Africa/ME  : Africa/Lagos Africa/Cairo Africa/Johannesburg
#                Asia/Jerusalem Asia/Dubai Asia/Riyadh
#   Asia       : Asia/Karachi Asia/Kolkata Asia/Dhaka Asia/Bangkok
#                Asia/Jakarta Asia/Singapore Asia/Hong_Kong Asia/Shanghai
#                Asia/Taipei Asia/Seoul Asia/Tokyo
#   Oceania    : Australia/Perth Australia/Adelaide Australia/Sydney
#                Pacific/Auckland Pacific/Honolulu

input=$(cat)

# Single jq call extracts all fields (tab-delimited)
read -r cwd agent model version cost duration lines_added lines_removed \
    tokens_in tokens_out remaining_pct exc_context <<< "$(echo "$input" | jq -r '[
    .workspace.current_dir,
    (.agent.type // "main"),
    .model.id,
    (.version // ""),
    (if .cost.total_cost_usd then (.cost.total_cost_usd * 100 | round / 100 | tostring) + "$" else "" end),
    (((.cost.total_api_duration_ms // 0) / 1000 / 60 | round | tostring) + "m"),
    (.cost.total_lines_added // 0 | tostring),
    (.cost.total_lines_removed // 0 | tostring),
    (((.context_window.total_input_tokens // 0) / 1000 | floor | tostring) + "k"),
    (((.context_window.total_output_tokens // 0) / 1000 | floor | tostring) + "k"),
    (if .context_window.current_usage.input_tokens then
        (.context_window.context_window_size // 200000) as $win |
        (.context_window.current_usage.input_tokens // 0) as $in |
        (.context_window.current_usage.cache_creation_input_tokens // 0) as $cc |
        (.context_window.current_usage.cache_read_input_tokens // 0) as $cr |
        (($in + $cc + $cr) / $win * 100) as $used |
        (100 - $used) | round
    else
        .context_window.remaining_percentage // 100
    end | tostring),
    (.exceeds_200k_tokens // false | tostring)
] | join("\t")')"

lines_changed="+${lines_added}/-${lines_removed}"
tokens="${tokens_in}/${tokens_out}"

# Subtract autocompact buffer to get TRUE usable space
# Priority: env var > observed default (16.5%)
if [ -n "$CLAUDE_AUTOCOMPACT_PCT_OVERRIDE" ]; then
    AUTOCOMPACT_BUFFER_PCT=$(awk "BEGIN {print 100 - $CLAUDE_AUTOCOMPACT_PCT_OVERRIDE}")
else
    # Docs claim CLAUDE_AUTOCOMPACT_PCT_OVERRIDE default is 95% (5% buffer),
    # but /context shows 16.5% buffer and compaction triggers at ~78-85% (issues #18264, #18241).
    # FIXME: Using observed 16.5% until Claude Code fixes the discrepancy.
    AUTOCOMPACT_BUFFER_PCT=16.5
fi

true_free_pct=$(awk "BEGIN {print $remaining_pct - $AUTOCOMPACT_BUFFER_PCT}")
remaining=$(echo "$true_free_pct" | awk '{printf "%.2f", $1/100}' | sed 's/^0\./\./')

# Color remaining based on TRUE free space threshold (warn when running LOW)
if [ "$(awk "BEGIN {print ($true_free_pct <= 10)}")" -eq 1 ]; then
    ctx_color="\\033[93;41m"  # Bright yellow fg, red bg - CRITICAL (≤10% usable)
elif [ "$(awk "BEGIN {print ($true_free_pct <= 20)}")" -eq 1 ]; then
    ctx_color="\\033[91;48;5;237m"  # Bright red fg, dark gray bg - WARNING (≤20% usable)
elif [ "$(awk "BEGIN {print ($true_free_pct <= 35)}")" -eq 1 ]; then
    ctx_color="\\033[93m"  # Yellow fg - CAUTION (≤35% usable)
else
    ctx_color="\\033[0;32m"   # Normal green fg - OK
fi

user=$(whoami)
time=$(date +%H:%M:%S)

# Build world-clock line. Source order:
#   1. $CC_WORLD_CLOCK env var (set in shell rc, requires CC restart to change)
#   2. ~/.claude/world-clock file content (live toggle — picked up on next render)
# If your local zone is in the list (e.g. Europe/Paris while in Paris) it will
# appear twice — omit it to avoid duplication.
clocks=""
zones_spec="${CC_WORLD_CLOCK:-$(cat "$HOME/.claude/world-clock" 2>/dev/null)}"
if [ -n "$zones_spec" ]; then
    IFS=',' read -ra _zones <<< "$zones_spec"
    for entry in "${_zones[@]}"; do
        tz="${entry%%=*}"
        label="${entry#*=}"
        [ "$label" = "$entry" ] && label="${tz##*/}"
        if [ -f "/usr/share/zoneinfo/$tz" ]; then
            clocks+=" ${label}:$(TZ="$tz" date +%H:%M)"
        else
            clocks+=" ?${tz}"
        fi
    done
fi

if git rev-parse --git-dir >/dev/null 2>&1; then
    branch=$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null)
    else branch=""
fi

printf "\\033[0;31magent:%s \\033[0;33mmodel:%s \\033[2mver:%s \\033[0;34mcost:%s \\033[0;36mdur:%s\\n\\033[0;32mlines:%s \\033[2mtokens(i/o):%s ${ctx_color}ctx(free):%s\\033[0m \\033[0;31m>200k:%s\\033[0m\\n\\033[2mdir:%s \\033[0;36mbranch:%s \\033[0;32muser:%s \\033[0;35mtime:%s\\033[0m" "$agent" "$model" "$version" "$cost" "$duration" "$lines_changed" "$tokens" "$remaining" "$exc_context" "$(basename "$cwd")" "$branch" "$user" "$time"

if [ -n "$clocks" ]; then
    printf "\\n\\033[0;35mclocks:%s\\033[0m" "$clocks"
fi
