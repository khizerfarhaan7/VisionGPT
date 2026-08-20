import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import faiss
import numpy as np

from app.evaluation.evaluation_service import EvaluationService


def create_synthetic_eval_workspace(temp_dir: Path) -> list:
    """
    Creates isolated synthetic vector stores for benchmark evaluation cases.
    Never modifies production indexes or user database data.
    """
    d = 384
    dirs = []

    # 1. PDF Vector Store
    pdf_dir = temp_dir / "pdf_doc"
    pdf_dir.mkdir()
    idx1 = faiss.IndexFlatL2(d)
    idx1.add(np.random.rand(2, d).astype("float32"))
    faiss.write_index(idx1, str(pdf_dir / "faiss.index"))
    with open(pdf_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump([
            {"chunk_id": "pdf_c1", "page": 1, "text": "Self-attention mechanisms allow transformers to process tokens concurrently."},
            {"chunk_id": "pdf_c2", "page": 2, "text": "Paper A concludes that self-attention improves parallelization efficiency."}
        ], f)
    dirs.append(pdf_dir)

    # 2. Audio Vector Store
    aud_dir = temp_dir / "audio" / "audio_rec"
    aud_dir.mkdir(parents=True)
    idx2 = faiss.IndexFlatL2(d)
    idx2.add(np.random.rand(1, d).astype("float32"))
    faiss.write_index(idx2, str(aud_dir / "faiss.index"))
    with open(aud_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump([
            {"chunk_id": "aud_c1", "start_time": 0.0, "end_time": 12.0, "text": "Welcome to the lecture recording on deep learning architectures."}
        ], f)
    dirs.append(aud_dir)

    # 3. Video Vector Store
    vid_dir = temp_dir / "video" / "vid_clip"
    vid_dir.mkdir(parents=True)
    idx3 = faiss.IndexFlatL2(d)
    idx3.add(np.random.rand(1, d).astype("float32"))
    faiss.write_index(idx3, str(vid_dir / "faiss.index"))
    with open(vid_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump([
            {"chunk_id": "vid_c1", "start_time": 0.0, "end_time": 15.0, "text": "0.0s-15.0s\nSpeech: Video slide presentation\nVision: Diagram showing projection matrix", "speech": "Video slide presentation", "vision": "Diagram showing projection matrix"}
        ], f)
    dirs.append(vid_dir)

    # 4. Image Vector Store
    img_dir = temp_dir / "image" / "chart_img"
    img_dir.mkdir(parents=True)
    idx4 = faiss.IndexFlatL2(d)
    idx4.add(np.random.rand(1, d).astype("float32"))
    faiss.write_index(idx4, str(img_dir / "faiss.index"))
    with open(img_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump([
            {"chunk_id": "img_c1", "text": "Diagram showing bar chart illustration graph."}
        ], f)
    dirs.append(img_dir)

    return dirs


async def main():
    parser = argparse.ArgumentParser(description="VisionGPT Evaluation & Benchmarking CLI")
    parser.add_argument(
        "--dataset",
        type=str,
        default="app/evaluation/datasets/benchmark_v1.json",
        help="Path to benchmark dataset JSON file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="app/evaluation/reports/latest_report.json",
        help="Path to save machine-readable evaluation report JSON"
    )
    parser.add_argument(
        "--compare-with",
        type=str,
        default=None,
        help="Path to previous evaluation report JSON for regression comparison"
    )

    args = parser.parse_args()
    dataset_path = Path(args.dataset)

    if not dataset_path.exists():
        print(f"Error: Dataset file not found at '{dataset_path}'")
        sys.exit(1)

    temp_dir = Path(tempfile.mkdtemp())
    try:
        eval_dirs = create_synthetic_eval_workspace(temp_dir)
        report = await EvaluationService.run_evaluation_suite(
            benchmark_path=dataset_path,
            vector_store_dirs=eval_dirs
        )

        # Save report JSON
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        # Print formatted Terminal Summary
        ret_m = report.get("retrieval_metrics", {})
        cite_m = report.get("citation_metrics", {})
        gnd_m = report.get("grounding_metrics", {})
        lat_m = report.get("latency_metrics", {})

        print("\n" + "=" * 52)
        print("VisionGPT Evaluation & Benchmarking Report")
        print(f"Dataset: {report.get('dataset')} ({report.get('total_cases')} test cases)")
        print("=" * 52)
        print(f"Overall Score:         {report.get('overall_score')} / 1.0")
        print("-" * 52)
        print(f"Retrieval Recall@5:    {ret_m.get('recall_at_k', 0.0) * 100:.1f}%")
        print(f"Precision@5:           {ret_m.get('precision_at_k', 0.0) * 100:.1f}%")
        print(f"MRR@5:                 {ret_m.get('mrr_at_k', 0.0):.2f}")
        print("-" * 52)
        print(f"Citation Recall:       {cite_m.get('citation_recall', 0.0) * 100:.1f}%")
        print(f"Citation Precision:    {cite_m.get('citation_precision', 0.0) * 100:.1f}%")
        print(f"Citation Completeness: {cite_m.get('citation_completeness', 0.0) * 100:.1f}%")
        print("-" * 52)
        print(f"Groundedness Proxy:    {gnd_m.get('groundedness_proxy_heuristic', 0.0) * 100:.1f}% (Heuristic)")
        print(f"Abstention Accuracy:   {gnd_m.get('abstention_accuracy', 0.0) * 100:.1f}%")
        print("-" * 52)
        print(f"Average Total Latency: {lat_m.get('mean_total_latency', 0.0):.2f}s")
        print("=" * 52)

        # Handle Regression Comparison if requested
        if args.compare_with:
            prev_path = Path(args.compare_with)
            if prev_path.exists():
                with open(prev_path, "r", encoding="utf-8") as pf:
                    prev_report = json.load(pf)
                comp = EvaluationService.compare_reports(report, prev_report)
                print("\nRegression Comparison Report:")
                print(f"Status:                 [{comp['status']}]")
                print(f"Overall Score Delta:    {comp['overall_score_change']:+.2f} (Current: {comp['current_score']}, Prev: {comp['previous_score']})")
                print(f"Retrieval Recall Delta: {comp['retrieval_recall_change']:+.2f}")
                print(f"Citation Prec Delta:    {comp['citation_precision_change']:+.2f}")
            else:
                print(f"\nWarning: Comparison report file not found at '{prev_path}'")

        print(f"\nMachine-readable report saved to: {out_path.resolve()}\n")

    finally:
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    asyncio.run(main())
