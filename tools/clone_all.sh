#!/bin/sh
# 并行浅克隆全部待审仓库（xargs 内联逻辑，兼容 BusyBox ash）
export https_proxy=http://127.0.0.1:7899 http_proxy=http://127.0.0.1:7899
DEST=/var/minis/shared/gen3audit/repos
mkdir -p "$DEST"
cat /var/minis/shared/gen3audit/repo_list.txt | xargs -P 6 -I{} sh -c '
  full="{}"; dir="'"$DEST"'/$(echo "{}" | tr "/" "_")"
  if [ -d "$dir/.git" ]; then echo "SKIP $full"; exit 0; fi
  for i in 1 2 3; do
    if git clone --depth 1 --quiet "https://github.com/$full.git" "$dir" 2>/dev/null; then
      echo "OK   $full"; exit 0
    fi
    rm -rf "$dir"; sleep 2
  done
  echo "FAIL $full"; exit 1
'
echo DONE
