from __future__ import annotations

import re
from pathlib import Path


class LeanProposalGenerator:
	"""
	Generates Lean proposal files in step-by-step fashion.

	Default output root is `<project_root>/.test`.
	"""

	def __init__(
		self,
		workspace_root: Path | None = None,
		output_root: Path | None = None,
		source_main_name: str = "main.lean",
		proposal_base_name: str = "main1",
	) -> None:
		self.workspace_root = workspace_root or Path(__file__).resolve().parents[4]
		self.output_root = output_root or (self.workspace_root / ".test")
		self.source_main = self.output_root / source_main_name
		self.proposal_base_name = proposal_base_name
		self.target_main = self.output_root / f"{proposal_base_name}.lean"

	def copy_main_to_proposal(self) -> str:
		self.output_root.mkdir(parents=True, exist_ok=True)
		if not self.source_main.exists():
			raise FileNotFoundError(f"Source file not found: {self.source_main}")

		original = self.source_main.read_text(encoding="utf-8")
		self.target_main.write_text(original, encoding="utf-8")
		return original

	def inject_local_lemma_and_theorem(self, main_content: str) -> str:
		_ = main_content.strip()
		return (
			"import Def\n\n"
			"lemma add_right_cancel_local (a b c : Nat) (h : a + c = b + c) : a = b := by\n"
			"  sorry\n\n"
			"theorem add_right_cancel_example : AddRightCancelGoal := by\n"
			"  intro a b c h\n"
			"  exact add_right_cancel_local a b c h\n"
		)

	@staticmethod
	def find_lemma_blocks(text: str) -> list[tuple[str, str, int, int]]:
		lines = text.splitlines(keepends=True)
		blocks: list[tuple[str, str, int, int]] = []
		index = 0

		while index < len(lines):
			line = lines[index]
			stripped = line.lstrip()

			if stripped.startswith("lemma "):
				start = index
				match = re.match(r"\s*lemma\s+([A-Za-z0-9_']+)", line)
				if not match:
					index += 1
					continue

				lemma_name = match.group(1)
				index += 1
				while index < len(lines):
					candidate = lines[index].lstrip()
					if candidate.startswith("lemma ") or candidate.startswith("theorem "):
						break
					index += 1

				end = index
				block_text = "".join(lines[start:end]).rstrip() + "\n"
				blocks.append((lemma_name, block_text, start, end))
				continue

			index += 1

		return blocks

	@staticmethod
	def build_stub_from_block(block_text: str) -> str:
		if ":= by" not in block_text:
			return block_text

		prefix = block_text.split(":= by", 1)[0].rstrip()
		return f"{prefix} := by\n  sorry\n"

	def extract_lemmas_to_new_files(self, main_text: str) -> str:
		lemma_blocks = self.find_lemma_blocks(main_text)
		if not lemma_blocks:
			self.target_main.write_text(main_text, encoding="utf-8")
			return main_text

		lines = main_text.splitlines(keepends=True)
		ranges_to_remove = {(start, end) for _, _, start, end in lemma_blocks}

		rebuilt_lines: list[str] = []
		line_index = 0
		while line_index < len(lines):
			skip_block = next((r for r in ranges_to_remove if r[0] == line_index), None)
			if skip_block is not None:
				line_index = skip_block[1]
				continue
			rebuilt_lines.append(lines[line_index])
			line_index += 1

		import_lines = [
			f"import {self.proposal_base_name}.{position}\n"
			for position in range(1, len(lemma_blocks) + 1)
		]
		body = "".join(rebuilt_lines).strip()
		final_main = "".join(import_lines) + ("\n" if import_lines else "") + body + "\n"

		for position, (_, block_text, _, _) in enumerate(lemma_blocks, start=1):
			lemma_file = self.output_root / f"{self.proposal_base_name}.{position}.lean"
			stub = self.build_stub_from_block(block_text)
			lemma_file.write_text(f"import Def\n\n{stub}", encoding="utf-8")

		self.target_main.write_text(final_main, encoding="utf-8")
		return final_main

	def run(self) -> None:
		print(f"Step 1: Copy {self.source_main.name} to {self.target_main.name}")
		main_content = self.copy_main_to_proposal()

		print("Step 2: Add local lemma with sorry and use it in add_right_cancel_example")
		updated = self.inject_local_lemma_and_theorem(main_content)
		self.target_main.write_text(updated, encoding="utf-8")

		print("Step 3: Extract introduced lemmas into main1.N.lean files and update imports")
		self.extract_lemmas_to_new_files(updated)

		print(f"Done. Generated proposal files in: {self.output_root}")


if __name__ == "__main__":
	LeanProposalGenerator().run()
