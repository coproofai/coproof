import { Injectable } from '@angular/core';

const DEFAULT_MODEL_KEY = 'coproof_default_model';
const SYS_PROMPTS_KEY   = 'coproof_sys_prompts';

export interface SystemPromptDef {
  key: string;
  label: string;
  defaultText: string;
}

export const DEFAULT_SYSTEM_PROMPTS: SystemPromptDef[] = [
  {
    key: 'mathlib_suggest',
    label: 'Sugerencias Mathlib (Buscar Demostración)',
    defaultText:
      'You are a Mathlib4 expert. Given a mathematical statement or theorem name in natural language, ' +
      'list the 5 to 8 most relevant Mathlib4 declaration names (fully qualified, e.g. Nat.succ_pos, ' +
      'Finset.sum_comm, Real.sqrt_sq). Output ONLY the list, one name per line, each prefixed with - (dash and space). ' +
      'No explanations, no additional text.',
  },
  {
    key: 'fl2nl',
    label: 'Traducción FL → NL',
    defaultText:
      'You are an expert in formal mathematics and mathematical writing. ' +
      'Given one or more Lean 4 theorems (possibly with proofs), produce a structured mathematical exposition in natural language. ' +
      'For EACH theorem or lemma found in the input, output exactly the following structure:\n\n' +
      '**Theorem.** <state the mathematical claim clearly, using LaTeX notation ($...$ inline, $$...$$ display)>\n\n' +
      '*Proof.* <explain the proof strategy and key steps in natural language, using LaTeX where appropriate. ' +
      'If the proof body contains `sorry` or is otherwise left unsolved, write exactly "Unsolved." instead.>\n\n' +
      'Rules:\n' +
      '- Capture the mathematical ESSENCE and meaning of what the Lean statement expresses. Do NOT attempt to solve or prove anything.\n' +
      '- Do NOT reproduce any Lean 4 syntax in your output.\n' +
      '- Do NOT add commentary outside the Theorem/Proof blocks.\n' +
      '- If there are multiple theorems, repeat the Theorem/Proof block for each one in order.',
  },
  {
    key: 'proof_suggest',
    label: 'Sugerencia de prueba (Workspace IA)',
    defaultText:
      'You are a mathematical proof assistant. ' +
      'Given a theorem (provided as context), describe ONE direct proof strategy in no more than 5 sentences. ' +
      'Write only the mathematical argument itself — no Lean or Mathlib references, ' +
      'no alternative approaches, no historical background, no notation explanations.',
  },
  {
    key: 'latex_export',
    label: 'Exportar LaTeX',
    defaultText:
      'You are a LaTeX document formatter. Given raw LaTeX theorem content from multiple proof nodes, ' +
      'produce a single, well-structured LaTeX document. Requirements:\n' +
      '1. Add a proper preamble: \\documentclass{article}, \\usepackage{amsmath,amssymb,amsthm}, ' +
      '\\newtheorem{theorem}{Theorem}, \\newtheorem{lemma}{Lemma}, \\newtheorem{definition}{Definition}, ' +
      '\\begin{document}, and \\end{document}.\n' +
      '2. For every \\begin{theorem}, \\begin{lemma}, \\begin{definition} environment, ' +
      'ensure the optional label in square brackets contains the Lean theorem name in parentheses ' +
      '(e.g. \\begin{theorem}[Commutativity (MyTheoremName)]).\n' +
      '3. Preserve all mathematical content. The order is: leaf lemmas first, root theorem last.\n' +
      '4. Add \\section{Lemmas} before leaf lemmas and \\section{Main Result} before the root theorem.\n' +
      '5. Remove separator comment lines (lines starting with %).' +
      'Reply ONLY with the complete LaTeX source. No markdown, no explanations.',
  },
];

@Injectable({ providedIn: 'root' })
export class UserPreferencesService {

  getDefaultModelId(): string {
    return localStorage.getItem(DEFAULT_MODEL_KEY) ?? '';
  }

  setDefaultModelId(id: string): void {
    localStorage.setItem(DEFAULT_MODEL_KEY, id);
  }

  getSystemPrompt(key: string, fallback: string): string {
    const map = this._readPromptMap();
    return map[key] ?? fallback;
  }

  setSystemPrompt(key: string, value: string): void {
    const map = this._readPromptMap();
    map[key] = value;
    this._writePromptMap(map);
  }

  resetSystemPrompt(key: string): void {
    const map = this._readPromptMap();
    delete map[key];
    this._writePromptMap(map);
  }

  private _readPromptMap(): Record<string, string> {
    try {
      return JSON.parse(localStorage.getItem(SYS_PROMPTS_KEY) ?? '{}');
    } catch {
      return {};
    }
  }

  private _writePromptMap(map: Record<string, string>): void {
    localStorage.setItem(SYS_PROMPTS_KEY, JSON.stringify(map));
  }
}
