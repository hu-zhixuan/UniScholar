"""
UniScholar 实验数据初步统计与科研可视化 Agent (Experimental Data Analysis & Visualization Agent)
支持上传科研实验数据（CSV / Excel / 文本），自动计算基础统计量、标记异常值、分析趋势，
并生成科研级可视化图表（折线图、箱线图、柱状图、分布图）及分析报告。
"""

import io
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # 保证无 GUI 环境平稳运行
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 设置中文字体与负号显示
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans", "Arial"]
plt.rcParams["axes.unicode_minus"] = False


class DataAgent:
    """
    实验数据统计与科研绘图智能体
    """

    def __init__(self, output_dir: str = "output/charts"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def load_data(self, file_path_or_content: str) -> pd.DataFrame:
        """加载 CSV / Excel 或原始文本数据"""
        if os.path.exists(file_path_or_content):
            ext = os.path.splitext(file_path_or_content)[1].lower()
            if ext in [".xlsx", ".xls"]:
                return pd.read_excel(file_path_or_content)
            else:
                try:
                    return pd.read_csv(file_path_or_content)
                except Exception:
                    return pd.read_csv(file_path_or_content, sep=r"\s+")
        else:
            # 尝试作为文本流读取
            return pd.read_csv(io.StringIO(file_path_or_content))

    def compute_basic_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """计算基础描述性统计量 (纯代码计算，零幻觉)"""
        numeric_df = df.select_dtypes(include=[np.number])
        if numeric_df.empty:
            return {"error": "数据中未检测到数值列"}

        desc = numeric_df.describe().to_dict()
        stats_summary = {}

        for col, col_stats in desc.items():
            stats_summary[col] = {
                "count": int(col_stats.get("count", 0)),
                "mean": round(float(col_stats.get("mean", 0.0)), 4),
                "std": round(float(col_stats.get("std", 0.0)), 4),
                "min": round(float(col_stats.get("min", 0.0)), 4),
                "q25": round(float(col_stats.get("25%", 0.0)), 4),
                "median": round(float(col_stats.get("50%", 0.0)), 4),
                "q75": round(float(col_stats.get("75%", 0.0)), 4),
                "max": round(float(col_stats.get("max", 0.0)), 4),
            }

        return stats_summary

    def detect_outliers_iqr(self, df: pd.DataFrame) -> Dict[str, Any]:
        """基于四分位距 (IQR) 法标记异常值"""
        numeric_df = df.select_dtypes(include=[np.number])
        outliers_report = {}

        for col in numeric_df.columns:
            series = numeric_df[col].dropna()
            if len(series) < 4:
                continue

            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            outliers = series[(series < lower_bound) | (series > upper_bound)]
            outlier_indices = outliers.index.tolist()
            outlier_values = [round(float(v), 4) for v in outliers.tolist()]

            outliers_report[col] = {
                "lower_bound": round(float(lower_bound), 4),
                "upper_bound": round(float(upper_bound), 4),
                "outlier_count": len(outliers),
                "outlier_indices": outlier_indices[:10],  # 最多记录前10个索引
                "outlier_values": outlier_values[:10],
            }

        return outliers_report

    def generate_scientific_charts(
        self,
        df: pd.DataFrame,
        task_id: str = "demo",
    ) -> List[str]:
        """
        根据数据特征自动绘制科研级高质量图表：
        1. 折线趋势图 (Trend Line Chart)
        2. 箱线图与异常值图 (Boxplot / Outlier Distribution)
        3. 分布直方图 (Histogram)
        """
        numeric_df = df.select_dtypes(include=[np.number])
        if numeric_df.empty:
            return []

        generated_charts = []
        cols = list(numeric_df.columns)[:4]  # 优先取前 4 个数值维度绘图

        # ---------------- 1. 折线趋势图 ----------------
        try:
            fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
            for col in cols:
                ax.plot(df.index, numeric_df[col], marker="o", markersize=3, label=col, linewidth=1.5)
            ax.set_title("科研实验数据指标趋势图 (Trend Analysis)", fontsize=13, pad=12, fontweight="bold")
            ax.set_xlabel("样本序号 / 实验轮次", fontsize=10)
            ax.set_ylabel("指标数值", fontsize=10)
            ax.grid(True, linestyle="--", alpha=0.6)
            ax.legend(loc="best", frameon=True)
            plt.tight_layout()

            line_path = os.path.join(self.output_dir, f"{task_id}_trend_line.png")
            fig.savefig(line_path)
            plt.close(fig)
            generated_charts.append(line_path)
        except Exception as e:
            logger.warning(f"生成折线图失败: {e}")

        # ---------------- 2. 箱线图 (异常值分布) ----------------
        try:
            fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
            box_data = [numeric_df[c].dropna() for c in cols]
            try:
                bplot = ax.boxplot(
                    box_data,
                    patch_artist=True,
                    tick_labels=cols,
                    flierprops={"marker": "x", "markerfacecolor": "red", "markeredgecolor": "red"},
                )
            except TypeError:
                bplot = ax.boxplot(
                    box_data,
                    patch_artist=True,
                    labels=cols,
                    flierprops={"marker": "x", "markerfacecolor": "red", "markeredgecolor": "red"},
                )

            # 美化箱体颜色
            colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]
            for patch, color in zip(bplot["boxes"], colors[:len(bplot["boxes"])]):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)

            ax.set_title("实验指标离散度与异常值标记箱线图 (Boxplot & Outliers)", fontsize=13, pad=12, fontweight="bold")
            ax.set_ylabel("分布范围", fontsize=10)
            ax.grid(True, linestyle="--", alpha=0.5)
            plt.tight_layout()

            box_path = os.path.join(self.output_dir, f"{task_id}_outlier_box.png")
            fig.savefig(box_path)
            plt.close(fig)
            generated_charts.append(box_path)
        except Exception as e:
            logger.warning(f"生成箱线图失败: {e}")

        # ---------------- 3. 分布直方图 ----------------
        try:
            primary_col = cols[0]
            fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
            ax.hist(numeric_df[primary_col].dropna(), bins=15, color="#348ABD", edgecolor="black", alpha=0.7)
            ax.set_title(f"核心指标 [{primary_col}] 频数分布直方图 (Distribution)", fontsize=13, pad=12, fontweight="bold")
            ax.set_xlabel(primary_col, fontsize=10)
            ax.set_ylabel("频数 (Frequency)", fontsize=10)
            ax.grid(True, linestyle="--", alpha=0.5)
            plt.tight_layout()

            hist_path = os.path.join(self.output_dir, f"{task_id}_distribution.png")
            fig.savefig(hist_path)
            plt.close(fig)
            generated_charts.append(hist_path)
        except Exception as e:
            logger.warning(f"生成直方图失败: {e}")

        return generated_charts

    def run(
        self,
        file_path_or_content: str,
        task_id: str = "demo",
    ) -> Dict[str, Any]:
        """全流程执行：数据加载 -> 统计分析 -> 异常值检测 -> 可视化绘图"""
        df = self.load_data(file_path_or_content)
        row_count, col_count = df.shape

        stats = self.compute_basic_statistics(df)
        outliers = self.detect_outliers_iqr(df)
        charts = self.generate_scientific_charts(df, task_id=task_id)

        # 组织 Markdown 格式的可视化统计报告
        report_lines = [
            "# 📊 科研实验数据统计分析与可视化报告\n",
            f"- **样本规模**: 共计 `{row_count}` 行数据，包含 `{col_count}` 个特征维度；",
            f"- **数值列数量**: `{len(stats)}` 列数值指标参与描述性统计。\n",
            "## 一、 核心描述性统计量指标表\n",
            "| 指标名称 | 样本量 (Count) | 均值 (Mean) | 标准差 (Std) | 最小值 (Min) | 中位数 (Median) | 最大值 (Max) |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for col, s in stats.items():
            report_lines.append(
                f"| `{col}` | {s['count']} | {s['mean']} | {s['std']} | {s['min']} | {s['median']} | {s['max']} |"
            )

        report_lines.append("\n## 二、 异常值检测与离群点审计 (IQR 规则)\n")
        has_outlier = False
        for col, o in outliers.items():
            if o["outlier_count"] > 0:
                has_outlier = True
                report_lines.append(
                    f"- ⚠️ 指标 **`{col}`** 检测到 `{o['outlier_count']}` 个离群异常值（正常范围阈值: `[{o['lower_bound']}, {o['upper_bound']}]`），代表性异常值样本: `{o['outlier_values']}`"
                )
        if not has_outlier:
            report_lines.append("✅ 各项指标数值分布平稳，未检测到显著偏离正常四分位区间的极端异常值。\n")

        report_lines.append("\n## 三、 科研可视化图表建议\n")
        report_lines.append(f"本智能体已根据数据特征自动渲染生成 `{len(charts)}` 张科研级可视化图表：\n")
        for idx, chart_path in enumerate(charts, 1):
            fname = os.path.basename(chart_path)
            report_lines.append(f"{idx}. **图表产物**: `{fname}` (已保存至 `{chart_path}`)")

        report_markdown = "\n".join(report_lines)

        return {
            "row_count": row_count,
            "col_count": col_count,
            "stats": stats,
            "outliers": outliers,
            "charts": charts,
            "report_markdown": report_markdown,
        }
