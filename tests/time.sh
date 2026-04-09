#!/bin/zsh -i

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 用法说明
usage() {
  echo -e "${CYAN}用法:${NC}"
  echo "  $0 [选项] <命令>"
  echo ""
  echo -e "${CYAN}选项:${NC}"
  echo "  -h, --help      显示帮助信息"
  echo "  -p, --precise   使用纳秒级精度（默认毫秒）"
  echo "  -q, --quiet     静默模式，只输出时间"
  echo "  -l, --log       记录到日志文件"
  echo "  -n, --no-exec   不实际执行，仅显示将要执行的命令"
  echo ""
  echo -e "${CYAN}示例:${NC}"
  echo "  $0 'sleep 2'"
  echo "  $0 -p 'curl https://api.example.com'"
  echo "  $0 -l 'make build'"
  echo "  $0 --quiet './benchmark.sh'"
}

# 格式化时间输出
format_time() {
  local total_seconds=$1
  local hours=$((total_seconds / 3600))
  local minutes=$(((total_seconds % 3600) / 60))
  local seconds=$((total_seconds % 60))
  local ms=$2

  local result=""
  [[ $hours -gt 0 ]] && result+="${hours}h "
  [[ $minutes -gt 0 ]] && result+="${minutes}m "
  [[ $seconds -gt 0 ]] && result+="${seconds}s"

  if [[ -n "$ms" && "$PRECISION" == "precise" ]]; then
    result+=" ${ms}ms"
  fi

  echo "${result:-0s}"
}

# 主计时函数
timer() {
  local cmd="$1"
  local start_time end_time elapsed_ms elapsed_sec

  # 显示执行的命令
  if [[ "$QUIET" != "true" ]]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}执行命令:${NC} $cmd"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  fi

  # 记录开始时间（纳秒级）
  if [[ "$PRECISION" == "precise" ]]; then
    start_time=$(date +%s%N)
  else
    start_time=$(date +%s%3N)
  fi

  # 执行命令并捕获退出码
  if [[ "$NO_EXEC" == "true" ]]; then
    echo -e "${YELLOW}[模拟执行] 命令未实际运行${NC}"
    exit_code=0
  else
    eval "$cmd"
    exit_code=$?
  fi

  # 记录结束时间
  if [[ "$PRECISION" == "precise" ]]; then
    end_time=$(date +%s%N)
    elapsed_ns=$((end_time - start_time))
    elapsed_ms=$((elapsed_ns / 1000000))
    elapsed_sec=$((elapsed_ns / 1000000000))
    remainder_ms=$(((elapsed_ns % 1000000000) / 1000000))
  else
    end_time=$(date +%s%3N)
    elapsed_ms=$((end_time - start_time))
    elapsed_sec=$((elapsed_ms / 1000))
    remainder_ms=$((elapsed_ms % 1000))
  fi

  # 显示结果
  if [[ "$QUIET" != "true" ]]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # 显示退出码
    if [[ $exit_code -eq 0 ]]; then
      echo -e "${GREEN}✓ 执行成功${NC} (退出码: $exit_code)"
    else
      echo -e "${RED}✗ 执行失败${NC} (退出码: $exit_code)"
    fi

    # 显示时间统计
    echo -e "${YELLOW}⏱  执行时间统计:${NC}"
    echo -e "   总毫秒数: ${CYAN}${elapsed_ms}${NC} ms"
    echo -e "   总秒数:   ${CYAN}${elapsed_sec}.${remainder_ms}${NC} s"
    echo -e "   格式化:   ${CYAN}$(format_time $elapsed_sec $remainder_ms)${NC}"

    # 性能评级
    if [[ $elapsed_ms -lt 100 ]]; then
      echo -e "   性能评级: ${GREEN}⚡ 极速${NC}"
    elif [[ $elapsed_ms -lt 1000 ]]; then
      echo -e "   性能评级: ${GREEN}🚀 快速${NC}"
    elif [[ $elapsed_ms -lt 10000 ]]; then
      echo -e "   性能评级: ${YELLOW}⏳ 一般${NC}"
    else
      echo -e "   性能评级: ${RED}🐌 较慢${NC}"
    fi

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  else
    # 静默模式只输出时间
    echo "${elapsed_ms}"
  fi

  # 记录日志
  if [[ "$LOG_MODE" == "true" ]]; then
    local log_file="timer_$(date +%Y%m%d).log"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] CMD: $cmd | Time: ${elapsed_ms}ms | Exit: $exit_code" >>"$log_file"
    [[ "$QUIET" != "true" ]] && echo -e "${CYAN}📝 已记录到:${NC} $log_file"
  fi

  return $exit_code
}

# 解析参数
PRECISION="normal"
QUIET="false"
LOG_MODE="false"
NO_EXEC="false"

while [[ $# -gt 0 ]]; do
  case $1 in
  -h | --help)
    usage
    exit 0
    ;;
  -p | --precise)
    PRECISION="precise"
    shift
    ;;
  -q | --quiet)
    QUIET="true"
    shift
    ;;
  -l | --log)
    LOG_MODE="true"
    shift
    ;;
  -n | --no-exec)
    NO_EXEC="true"
    shift
    ;;
  --)
    shift
    break
    ;;
  -*)
    echo -e "${RED}错误: 未知选项 $1${NC}" >&2
    usage
    exit 1
    ;;
  *)
    break
    ;;
  esac
done

# 检查是否有命令
if [[ $# -eq 0 ]]; then
  echo -e "${RED}错误: 请提供要执行的命令${NC}" >&2
  usage
  exit 1
fi

# 执行计时
timer "$*"
