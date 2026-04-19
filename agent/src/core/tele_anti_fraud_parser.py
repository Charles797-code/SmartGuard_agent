"""
TeleAntiFraud-28k 全量原始数据提取器
将所有原始数据直接提取为纯文本，供向量库向量化
无需解析标签，完整保留原始信息让 LLM 自行判断
"""

import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field, asdict


@dataclass
class RawCase:
    """原始案例（未处理，保持原样）"""
    case_id: str
    content: str          # 主文本内容（用于向量检索）
    raw_json: str         # 原始 JSON（保留一切信息）
    source: str           # 来源描述
    source_path: str      # 文件路径
    dataset: str          # 数据集分类

    # 元数据（可直接使用）
    is_fraud: bool = False
    fraud_type: str = ""
    confidence: float = 0.0
    scene: str = ""
    reason: str = ""
    audio_path: str = ""


class TeleAntiFraudExtractor:
    """
    全量提取 TeleAntiFraud-28k 原始数据
    不做标签解析，直接输出原始文本 + 原始 JSON
    """

    def __init__(self, dataset_root: str):
        self.dataset_root = Path(dataset_root)
        self.cases: List[RawCase] = []

    def _extract_labels_from_answer(self, content: str) -> Dict[str, Any]:
        """从 answer 块中提取标签（如果存在）"""
        result = {
            "is_fraud": False,
            "fraud_type": "",
            "confidence": 0.0,
            "scene": "",
            "reason": ""
        }

        match = re.search(r'<answer>\s*(.*?)\s*</answer>', content, re.DOTALL)
        if not match:
            return result

        try:
            json_match = re.search(r'```json\s*(.*?)\s*```', match.group(1), re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                result["is_fraud"] = bool(data.get("is_fraud", False))
                result["fraud_type"] = str(data.get("fraud_type", ""))
                result["confidence"] = float(data.get("confidence", 0.0))
                result["scene"] = str(data.get("scene", ""))
                result["reason"] = str(data.get("reason", ""))
        except (json.JSONDecodeError, ValueError):
            pass

        return result

    def _messages_to_text(self, messages: List[Dict]) -> str:
        """把 messages 转成易读文本"""
        parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                continue

            # 去掉 audio 标签和 prompt（只保留对话文本）
            content = re.sub(r'<audio>.*?</audio>', '', content, flags=re.DOTALL)
            content = re.sub(r'\*\*音频.*?\*\*', '', content)
            content = re.sub(r'\*\*对话音频：.*?\*\*', '', content)
            content = content.strip()

            if not content:
                continue

            # 去掉 prompt 模板（系统指令太长，不适合向量检索）
            if '```json' in content and '<answer>' not in content:
                # 这是 prompt，提取其中的对话文本
                # 尝试提取对话内容
                text_parts = re.findall(r'role.*?content.*?"([^"]{10,})"', content, re.DOTALL)
                if text_parts:
                    content = ' '.join(text_parts[:10])
                else:
                    continue

            if role == "user":
                parts.append(f"【骗子】{content}")
            elif role == "assistant":
                parts.append(f"【客服】{content}")

        return "\n".join(parts)

    def _extract_from_config_json(self, config_path: Path) -> str:
        """从 config.json 提取对话文本"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            segments = config.get("audio_segments", [])
            parts = []
            for seg in segments:
                role = seg.get("role", "")
                content = seg.get("content", "")
                if content and role in ("left", "right"):
                    label = "骗子" if role == "left" else "客服"
                    parts.append(f"【{label}】{content}")

            return "\n".join(parts)
        except Exception:
            return ""

    def parse_jsonl(self, file_path: Path, dataset: str) -> List[RawCase]:
        """解析 jsonl 文件"""
        cases = []
        idx = 0

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    messages = entry.get("messages", [])
                    if not messages:
                        continue

                    # 对话文本
                    text = self._messages_to_text(messages)
                    if len(text) < 30:
                        continue

                    # 提取标签
                    labels = {"is_fraud": False, "fraud_type": "", "confidence": 0.0, "scene": "", "reason": ""}
                    for msg in reversed(messages):
                        if msg.get("role") == "assistant":
                            labels = self._extract_labels_from_answer(msg.get("content", ""))
                            break

                    # 音频路径
                    audios = entry.get("audios", [])
                    audio_path = audios[0] if audios else ""

                    # 来源描述
                    source_desc = f"{dataset}/{file_path.stem}"

                    cases.append(RawCase(
                        case_id=f"{dataset}_{file_path.stem}_{idx}",
                        content=text,
                        raw_json=json.dumps(entry, ensure_ascii=False)[:5000],
                        source=source_desc,
                        source_path=str(file_path),
                        dataset=dataset,
                        is_fraud=labels["is_fraud"],
                        fraud_type=labels["fraud_type"],
                        confidence=labels["confidence"],
                        scene=labels["scene"],
                        reason=labels["reason"],
                        audio_path=audio_path,
                    ))
                    idx += 1

        except Exception as e:
            print(f"  解析失败 {file_path}: {e}")

        return cases

    def parse_merged_result(self) -> List[RawCase]:
        """解析 merged_result 目录"""
        cases = []
        merged_dir = self.dataset_root / "merged_result"

        if not merged_dir.exists():
            print(f"  merged_result 目录不存在，跳过")
            return cases

        idx = 0
        for subdir in sorted(merged_dir.iterdir()):
            if not subdir.is_dir():
                continue

            is_fraud = "NEG" in subdir.name  # NEG = 诈骗，POS = 正常

            for tts_dir in sorted(subdir.iterdir()):
                if not tts_dir.is_dir() or not tts_dir.name.startswith("tts_test"):
                    continue

                config_path = tts_dir / "config.json"
                if not config_path.exists():
                    continue

                text = self._extract_from_config_json(config_path)
                if len(text) < 20:
                    continue

                # 读取原始 JSON（截断以节省空间）
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        raw_json = f.read()[:5000]
                except Exception:
                    raw_json = ""

                # 从 config 获取终止信息
                terminated = False
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    terminated = config.get("terminated_by_manager", False)
                    end_call = config.get("end_call_signal_detected", False)
                    term_reason = config.get("termination_reason", "")
                    reason = f"通话终止状态: terminated={terminated}, end_call={end_call}, reason={term_reason}"
                except Exception:
                    reason = ""
                    term_reason = ""

                cases.append(RawCase(
                    case_id=f"merged_{subdir.name}_{tts_dir.name}",
                    content=text,
                    raw_json=raw_json,
                    source=f"merged/{subdir.name}",
                    source_path=str(tts_dir),
                    dataset="merged",
                    is_fraud=is_fraud,
                    fraud_type="",
                    confidence=0.95 if terminated else (0.7 if is_fraud else 0.9),
                    scene="",
                    reason=reason,
                    audio_path=str(tts_dir / f"{tts_dir.name}.mp3"),
                ))
                idx += 1

        return cases

    def parse_official_docu(self) -> List[RawCase]:
        """解析官方反诈文档"""
        cases = []
        docu_dir = self.dataset_root.parent / "official_docu"

        if not docu_dir.exists():
            print(f"  official_docu 目录不存在，跳过")
            return cases

        for subdir in docu_dir.iterdir():
            if not subdir.is_dir():
                continue

            for json_file in sorted(subdir.iterdir()):
                if json_file.suffix != ".json":
                    continue

                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    website_name = data.get("website_name", json_file.stem)
                    source_data = data.get("source_data", [])

                    if isinstance(source_data, list):
                        for i, item in enumerate(source_data):
                            if not isinstance(item, dict):
                                continue

                            title = item.get("title", "")
                            content = item.get("content", "")
                            if len(content) < 50:
                                continue

                            cases.append(RawCase(
                                case_id=f"docu_{json_file.stem}_{i}",
                                content=f"【{title}】\n{content}",
                                raw_json=json.dumps(item, ensure_ascii=False)[:5000],
                                source=f"官方文档/{website_name}",
                                source_path=str(json_file),
                                dataset="official_docu",
                                is_fraud=True,  # 官方文档里的都是已核实诈骗
                                fraud_type="",
                                confidence=0.99,
                                scene="",
                                reason="官方反诈案例库中已核实的诈骗案例",
                                audio_path="",
                            ))
                except Exception as e:
                    print(f"  解析文档失败 {json_file}: {e}")

        return cases

    def load_all(self, max_per_file: int = 0) -> List[RawCase]:
        """
        加载所有原始数据

        Args:
            max_per_file: 每个文件最大条数（0=不限）
        """
        all_cases = []

        # 1. 主要 jsonl 文件
        jsonl_files = [
            ("total_train.jsonl", "train"),
            ("total_train_clear.jsonl", "train"),
            ("total_train_swift3_demo.jsonl", "train"),
            ("total_test.jsonl", "test"),
            ("total_test_swift3.jsonl", "test"),
        ]

        for fname, dataset in jsonl_files:
            fpath = self.dataset_root / fname
            if fpath.exists():
                print(f"解析 {fname}...")
                cases = self.parse_jsonl(fpath, dataset)
                if max_per_file > 0:
                    cases = cases[:max_per_file]
                print(f"  → {len(cases)} 条")
                all_cases.extend(cases)

        # 2. merged_result（大量对话数据）
        print("解析 merged_result（大量对话数据）...")
        merged_cases = self.parse_merged_result()
        print(f"  → {len(merged_cases)} 条")
        all_cases.extend(merged_cases)

        # 3. 官方文档
        print("解析 official_docu（官方反诈案例）...")
        docu_cases = self.parse_official_docu()
        print(f"  → {len(docu_cases)} 条")
        all_cases.extend(docu_cases)

        self.cases = all_cases
        print(f"\n总计: {len(all_cases)} 条原始案例")
        return all_cases

    def get_stats(self) -> Dict[str, Any]:
        if not self.cases:
            return {}

        datasets: Dict[str, int] = {}
        for c in self.cases:
            datasets[c.dataset] = datasets.get(c.dataset, 0) + 1

        total_chars = sum(len(c.content) for c in self.cases)

        return {
            "total": len(self.cases),
            "by_dataset": datasets,
            "total_chars": total_chars,
            "avg_chars": total_chars / len(self.cases) if self.cases else 0,
        }

    def export(self, output_path: str):
        """导出为 JSONL"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for case in self.cases:
                f.write(json.dumps(asdict(case), ensure_ascii=False) + '\n')
        print(f"已导出 {len(self.cases)} 条到 {output_path}")


if __name__ == "__main__":
    ext = TeleAntiFraudExtractor(r"D:\new\agentnew\agentnew\agent\knowledge_base\TeleAntiFraud-28k")
    ext.load_all()
    stats = ext.get_stats()
    print(f"\n统计: {json.dumps(stats, ensure_ascii=False, indent=2)}")
    ext.export(r"D:\new\agentnew\agentnew\agent\knowledge_base\TeleAntiFraud-28k\all_raw_cases.jsonl")
