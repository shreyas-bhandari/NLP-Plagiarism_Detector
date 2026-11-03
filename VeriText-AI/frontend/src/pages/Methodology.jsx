import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  Braces,
  Database,
  ExternalLink,
  FileWarning,
  Layers,
  Lock,
  Ruler,
  Scale,
  ScanText,
  Sigma,
  SplitSquareVertical,
  TriangleAlert,
} from 'lucide-react'
import { Callout } from '../components/Primitives'

/** Evaluation numbers are produced by backend/evaluation/evaluate.py on 59 labelled pairs. */
const CATEGORY_STATS = [
  { category: 'Identical', n: 8, min: 1.0, median: 1.0, max: 1.0 },
  { category: 'Lightly modified', n: 8, min: 0.917, median: 0.989, max: 0.996 },
  { category: 'Paraphrase', n: 10, min: 0.262, median: 0.543, max: 0.679 },
  { category: 'Semantically similar (different claim)', n: 8, min: 0.24, median: 0.512, max: 0.553 },
  { category: 'Common academic phrasing', n: 10, min: 0.678, median: 0.804, max: 0.98 },
  { category: 'Technical definition', n: 7, min: 0.631, median: 0.913, max: 0.961 },
  { category: 'Unrelated', n: 8, min: -0.086, median: -0.025, max: 0.059 },
]

const RULE_STATS = [
  {
    rule: 'Naive cosine threshold (0.62)',
    precision: '0.528',
    recall: '0.731',
    f1: '0.613',
    note: 'Baseline: any pair above the threshold counts as reuse.',
  },
  {
    rule: 'Cosine OR near-exact lexical, best F1 (threshold 0.45)',
    precision: '0.521',
    recall: '0.962',
    f1: '0.676',
    note: 'High recall, but admits most boilerplate at that threshold.',
  },
  {
    rule: 'VeriText production rule (0.62)',
    precision: '0.576',
    recall: '0.731',
    f1: '0.644',
    note: 'Exact/near-exact evidence plus safeguarded semantic matches.',
  },
]

function Section({ id, icon: Icon, title, children }) {
  return (
    <section id={id} className="scroll-mt-24 border-t border-navy-100 py-7 first:border-t-0 first:pt-0">
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-navy-50 text-navy-600">
          <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
        <h2 className="text-[16px] font-semibold tracking-[-0.01em] text-navy-900">{title}</h2>
      </div>
      <div className="mt-3 space-y-3 text-[13px] leading-relaxed text-navy-600">{children}</div>
    </section>
  )
}

function Formula({ children, caption }) {
  return (
    <div className="rounded-lg border border-navy-200 bg-navy-50/60 px-4 py-3">
      <p className="font-mono text-[13px] text-navy-900">{children}</p>
      {caption && <p className="mt-1.5 text-[11.5px] leading-snug text-navy-500">{caption}</p>}
    </div>
  )
}

export default function Methodology() {
  return (
    <div className="mx-auto max-w-[900px]">
      <div className="flex items-center gap-2 text-[11.5px] text-navy-400">
        <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />
        About VeriText AI
      </div>
      <h1 className="mt-1 text-[24px] font-semibold tracking-[-0.02em] text-navy-900">
        Methodology, evaluation and limits
      </h1>
      <p className="mt-2 max-w-2xl text-[13.5px] leading-relaxed text-navy-500">
        This page explains exactly how a VeriText AI comparison is produced: how text is extracted,
        how sentences become vectors, how similarity is scored, what the safeguards do, what the
        evaluation actually measured, and where the approach fails. Nothing here is a vendor claim —
        the numbers come from a script shipped with the project.
      </p>

      <div className="mt-4">
        <Callout tone="disclaimer" title="The one sentence to remember">
          A similarity score describes textual and semantic overlap between two documents. It is not
          a plagiarism percentage and it is never, on its own, evidence of misconduct.
        </Callout>
      </div>

      <div className="mt-6">
        <Section icon={SplitSquareVertical} title="1. Pipeline overview" id="pipeline">
          <p>
            Each comparison runs the same five deterministic stages: extraction → segmentation →
            embedding → similarity scoring → classification &amp; explanation. There is no training
            step, no external API call and no randomness: the same two documents always produce the
            same scores.
          </p>
          <ol className="grid gap-2 sm:grid-cols-2">
            {[
              { icon: ScanText, label: 'Extract text', body: 'PyMuPDF for PDF, python-docx for DOCX, always with paragraph positions.' },
              { icon: Braces, label: 'Segment', body: 'Abbreviation-aware sentence split; headings, references and fragments set aside.' },
              { icon: Sigma, label: 'Embed', body: 'Batched MiniLM encoding into L2-normalised 384-d vectors.' },
              { icon: Layers, label: 'Classify', body: 'Cosine + lexical evidence → exact / near-exact / semantic, with safeguards.' },
            ].map(({ icon: Icon, label, body }) => (
              <li key={label} className="rounded-lg border border-navy-100 bg-white p-3">
                <p className="flex items-center gap-1.5 text-[12.5px] font-semibold text-navy-900">
                  <Icon className="h-3.5 w-3.5 text-accent-600" aria-hidden="true" />
                  {label}
                </p>
                <p className="mt-1 text-[11.5px] leading-snug text-navy-500">{body}</p>
              </li>
            ))}
          </ol>
        </Section>

        <Section icon={Braces} title="2. Segmentation and normalisation" id="segmentation">
          <p>
            Sentence boundaries are found with a rule-based splitter that protects abbreviations
            (<span className="font-mono text-[12px]">et al.</span>,{' '}
            <span className="font-mono text-[12px]">e.g.</span>,{' '}
            <span className="font-mono text-[12px]">Fig.</span>), initials and decimal numbers. It
            runs offline and deterministically, which keeps sentence indices reproducible across runs.
          </p>
          <p>
            Text is normalised for presentation (whitespace, control characters, unicode width) but
            <strong> stop words are not removed and no stemming is applied before embedding</strong>.
            Sentence-Transformers depend on full context; aggressive cleaning would damage the
            meaning signal. A separate stemmed content-token view exists only for the lexical
            comparison path and for showing which words two sentences share.
          </p>
        </Section>

        <Section icon={Sigma} title="3. Sentence embeddings" id="embeddings">
          <p>
            Every sentence is encoded by{' '}
            <span className="font-mono text-[12px]">sentence-transformers/all-MiniLM-L6-v2</span>, a
            6-layer transformer distilled from larger models. The encoder reads the token sequence,
            produces a contextual vector per token, and mean-pools them into one 384-dimensional
            vector, which is then L2-normalised.
          </p>
          <Formula caption="Each sentence becomes a point on the unit hypersphere; related meanings cluster together.">
            sentence → [CLS] t₁ … tₙ [SEP] → encoder → mean-pool → v ∈ ℝ³⁸⁴, ‖v‖ = 1
          </Formula>
          <p>
            The model is loaded once when the backend starts and reused for every request. Encoding
            runs in batches (16 sentences per batch on a GPU so a 4 GB laptop card keeps headroom,
            32 on CPU — both configurable) inside <code className="rounded bg-navy-100 px-1 py-0.5 font-mono text-[11.5px] text-navy-800">torch.inference_mode()</code>, and identical
            sentence text is cached, so repeated analyses never recompute unchanged sentences.
          </p>
          <p>
            <strong>Device selection.</strong> The backend resolves its device at startup —{' '}
            <code className="rounded bg-navy-100 px-1 py-0.5 font-mono text-[11.5px] text-navy-800">cuda</code> when a CUDA-enabled PyTorch build can actually see a GPU,{' '}
            <code className="rounded bg-navy-100 px-1 py-0.5 font-mono text-[11.5px] text-navy-800">cpu</code> otherwise — and reports the real values on{' '}
            <code className="rounded bg-navy-100 px-1 py-0.5 font-mono text-[11.5px] text-navy-800">GET /api/health</code> (the active device also appears in the sidebar badge).
            If CUDA runs out of memory mid-analysis the batch is halved and the step retried; if a
            single sentence still does not fit, the model moves to CPU for the rest of the session
            and the reason is recorded rather than the analysis failing.
          </p>
        </Section>

        <Section icon={Ruler} title="4. Cosine similarity" id="cosine">
          <p>
            Two sentences are compared by the cosine of the angle between their vectors. Because both
            vectors are unit length, this is exactly their dot product — the engine computes it as a
            matrix product, which is why it can score thousands of pairs per second on a single
            CPU or GPU.
          </p>
          <Formula caption="cos = 1 means identical direction; cos ≈ 0 means unrelated; negative values mean opposing direction (rare for sentences).">
            cos(A, B) = (A · B) / (‖A‖ · ‖B‖) = A · B
          </Formula>
          <p>
            For each comparable sentence, the engine retrieves the <em>k</em> most similar sentences in
            the other document (k = 3 by default) using a partial selection rather than a full sort,
            so memory stays bounded on long documents. Cosine similarity is a measure of
            <em> relatedness</em>, not of copying — a shared topic also raises it.
          </p>
          <p>
            <strong>Paragraph level.</strong> A paragraph vector is the mean of its sentence vectors,
            re-normalised to unit length. Paragraph pairs are compared the same way and displayed
            separately, because an argument block can be reused even when individual sentences are
            rewritten below the sentence threshold. In the other direction, when one sentence closely
            matches several sentences in the other document, only its best match counts as primary
            evidence — the alternatives are kept for the reviewer and never added to the totals, so a
            many-to-one overlap cannot inflate the index.
          </p>
        </Section>

        <Section icon={Layers} title="5. Classification: exact, near-exact, semantic" id="classification">
          <p>
            Cosine alone cannot tell a copied sentence from a shared definition, so each candidate
            pair is also compared lexically: normalised string equality, a token-sequence ratio
            (difflib), token Jaccard overlap and the longest verbatim run.
          </p>
          <div className="overflow-hidden rounded-lg border border-navy-200">
            <table className="w-full border-collapse text-[12px]">
              <thead>
                <tr className="bg-navy-50 text-left">
                  <th className="px-3 py-2 font-semibold text-navy-700">Class</th>
                  <th className="px-3 py-2 font-semibold text-navy-700">Rule</th>
                  <th className="px-3 py-2 font-semibold text-navy-700">What it means</th>
                </tr>
              </thead>
              <tbody className="text-navy-600">
                <tr className="border-t border-navy-100">
                  <td className="px-3 py-2 font-semibold text-red-700">Exact</td>
                  <td className="px-3 py-2">identical after normalisation</td>
                  <td className="px-3 py-2">Same words, same order (case and punctuation ignored).</td>
                </tr>
                <tr className="border-t border-navy-100">
                  <td className="px-3 py-2 font-semibold text-amber-700">Near-exact</td>
                  <td className="px-3 py-2">token sequence ratio ≥ 0.85</td>
                  <td className="px-3 py-2">A few words changed, added or removed.</td>
                </tr>
                <tr className="border-t border-navy-100">
                  <td className="px-3 py-2 font-semibold text-accent-700">Semantic</td>
                  <td className="px-3 py-2">cosine ≥ 0.62</td>
                  <td className="px-3 py-2">Different wording, related meaning — potential paraphrase.</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p>
            Bands used for display: 90–100% very high, 80–89% high, 65–79% moderate, below 65% low.
            These are configurable operating points, not scientifically validated plagiarism
            boundaries; the threshold can be changed per analysis.
          </p>
        </Section>

        <Section icon={Scale} title="6. Coverage metrics and the similarity index" id="metrics">
          <p>
            Averaging all pairwise cosines would be meaningless (most pairs are unrelated). Instead
            the engine reports:
          </p>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              <strong>Sentence coverage</strong> — share of comparable sentences in a document that
              have at least one qualifying match.
            </li>
            <li>
              <strong>Word coverage</strong> — share of words inside matched sentences.
            </li>
            <li>
              <strong>Average matched similarity</strong> — the best score of each matched sentence
              in Document A, averaged. A sentence matched by several candidates counts once, at its
              strongest score.
            </li>
            <li>
              <strong>Coverage-weighted similarity index</strong> — the headline number.
            </li>
          </ul>
          <Formula caption="Each sentence contributes at most once, at its best score, so the index is always between 0% and 100%. Unmatched sentences contribute zero: coverage and closeness are combined into one interpretable value. It is explicitly not called a plagiarism percentage.">
            index = Σ (best cosine of each matched sentence in A, counted once) ÷ (comparable sentences in A)
          </Formula>
          <p>
            Counts use the <em>best</em> match per sentence, so one sentence matching six others
            cannot inflate the result; the extra candidates remain available as alternative evidence.
            Matching also runs in the reverse direction (B→A) so that sentences unique to Document B
            are still covered and visible. Those reverse matches add to <strong>B's coverage</strong>
            but never to A's index — the same evidence is never added twice, which is what keeps the
            headline number inside 0–100%.
            Matches are also grouped into <strong>passages</strong>: consecutive matching sentences
            are clustered, because genuine reused material arrives in runs while boilerplate arrives
            as isolated hits.
          </p>
        </Section>

        <Section icon={FileWarning} title="7. Safeguards against misleading matches" id="safeguards">
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <strong>Reference lists and bibliographies</strong> are detected and excluded by
              default — they repeat verbatim across papers and would swamp any score.
            </li>
            <li>
              <strong>Headings and very short fragments</strong> (fewer than five words or 25
              characters) are shown but never compared.
            </li>
            <li>
              <strong>Generic academic phrasing</strong> — a pair whose only shared content words are
              generic vocabulary (&ldquo;method&rdquo;, &ldquo;results&rdquo;, &ldquo;further research
              is needed&rdquo;) is downgraded to weak evidence, and suppressed entirely when its
              similarity is below the high band.
            </li>
            <li>
              <strong>Citation-only overlap</strong> — if the shared words vanish once citations are
              stripped, the match is suppressed.
            </li>
            <li>
              <strong>Definition-shaped pairs</strong> (&ldquo;X is …&rdquo;) are reported but
              annotated, because textbook definitions are often phrased identically.
            </li>
            <li>
              <strong>Nothing is hidden:</strong> suppressed pairs stay in the result with a reason,
              excluded only from the headline counts.
            </li>
          </ul>
        </Section>

        <Section icon={Database} title="8. What the evaluation measured" id="evaluation">
          <p>
            The repository includes {59} hand-labelled sentence pairs across seven categories and a
            script (<span className="font-mono text-[12px]">backend/evaluation/evaluate.py</span>) that
            runs the real model on them. Mean cosine by category:
          </p>
          <div className="overflow-hidden rounded-lg border border-navy-200">
            <table className="w-full border-collapse text-[12px]">
              <thead>
                <tr className="bg-navy-50 text-left">
                  <th className="px-3 py-2 font-semibold text-navy-700">Category</th>
                  <th className="px-3 py-2 text-right font-semibold text-navy-700">n</th>
                  <th className="px-3 py-2 text-right font-semibold text-navy-700">min</th>
                  <th className="px-3 py-2 text-right font-semibold text-navy-700">median</th>
                  <th className="px-3 py-2 text-right font-semibold text-navy-700">max</th>
                </tr>
              </thead>
              <tbody className="text-navy-600">
                {CATEGORY_STATS.map((row) => (
                  <tr key={row.category} className="border-t border-navy-100">
                    <td className="px-3 py-1.5">{row.category}</td>
                    <td className="tnum px-3 py-1.5 text-right">{row.n}</td>
                    <td className="tnum px-3 py-1.5 text-right">{row.min.toFixed(3)}</td>
                    <td className="tnum px-3 py-1.5 text-right">{row.median.toFixed(3)}</td>
                    <td className="tnum px-3 py-1.5 text-right">{row.max.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>
            The distribution is the key result: <strong>boilerplate and definitions score higher than
            heavy paraphrase</strong>. Paraphrased pairs sit at 0.26–0.68 while common academic
            phrases sit at 0.68–0.98. That is why a single threshold cannot be a plagiarism verdict,
            and why the engine reports evidence classes and safeguards instead of one percentage.
          </p>
          <p>
            Treating &ldquo;identical + lightly modified + paraphrased&rdquo; as the positive class
            (26 pairs) and everything else as negative (33 pairs):
          </p>
          <div className="overflow-hidden rounded-lg border border-navy-200">
            <table className="w-full border-collapse text-[12px]">
              <thead>
                <tr className="bg-navy-50 text-left">
                  <th className="px-3 py-2 font-semibold text-navy-700">Decision rule</th>
                  <th className="px-3 py-2 text-right font-semibold text-navy-700">P</th>
                  <th className="px-3 py-2 text-right font-semibold text-navy-700">R</th>
                  <th className="px-3 py-2 text-right font-semibold text-navy-700">F1</th>
                </tr>
              </thead>
              <tbody className="text-navy-600">
                {RULE_STATS.map((row) => (
                  <tr key={row.rule} className="border-t border-navy-100">
                    <td className="px-3 py-2">
                      {row.rule}
                      <span className="block text-[11px] text-navy-400">{row.note}</span>
                    </td>
                    <td className="tnum px-3 py-2 text-right">{row.precision}</td>
                    <td className="tnum px-3 py-2 text-right">{row.recall}</td>
                    <td className="tnum px-3 py-2 text-right font-semibold">{row.f1}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[12.5px] text-navy-500">
            On semantic relatedness (34 related vs 25 unrelated pairs) the model separates the classes
            almost perfectly: precision 1.00, recall 0.96, F1 0.98 at a 0.40 threshold. The model
            understands meaning well; deciding what counts as <em>misconduct</em> is a different
            question that no threshold answers.
          </p>
          <p>
            Instructions to reproduce:{' '}
            <span className="font-mono text-[12px]">cd backend &amp;&amp; python evaluation/evaluate.py --markdown</span>
            .
          </p>
        </Section>

        <Section icon={TriangleAlert} title="9. Limitations" id="limitations">
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <strong>Two documents only.</strong> VeriText AI does not search the web or a corpus; it
              cannot find a source you did not supply.
            </li>
            <li>
              <strong>Heavy paraphrase is the weak spot.</strong> MiniLM-scale embeddings often score
              well-rewritten text around 0.45–0.60, below the default flag threshold.
            </li>
            <li>
              <strong>Legitimate similarity is common.</strong> Definitions, standard methods, shared
              data descriptions and quotations all raise similarity. Discipline-specific terminology
              can dominate an embedding.
            </li>
            <li>
              <strong>Segmentation matters.</strong> Different sentence boundaries shift scores by
              several points; very short sentences are unstable.
            </li>
            <li>
              <strong>Extraction is imperfect.</strong> Tables, equations, footnotes and multi-column
              layouts lose structure; scanned PDFs need OCR first.
            </li>
            <li>
              <strong>The evaluation set is small (59 pairs) and author-labelled.</strong> It is an
              engineering sanity check, not benchmark evidence, and single pairs move the metrics.
            </li>
            <li>
              <strong>No verdict.</strong> Nothing in the output establishes intent, and the interface
              repeatedly says so on purpose.
            </li>
          </ul>
        </Section>

        <Section icon={Lock} title="10. Privacy and data handling" id="privacy">
          <ul className="list-disc space-y-1.5 pl-5">
            <li>Uploads are validated, written to a private temp file, extracted, then deleted immediately.</li>
            <li>Uploaded content is never executed, rendered or interpreted as code.</li>
            <li>
              Extracted text is kept only in a TTL session store (default 120 minutes) so the
              side-by-side viewer can render it, then purged automatically.
            </li>
            <li>
              The database stores analysis metadata, scores and short snippet excerpts — not full
              documents. Deleting an analysis removes its text immediately.
            </li>
            <li>
              No third-party service receives your documents; inference runs locally in this
              process — on the GPU when a CUDA-capable device is detected, otherwise on the CPU.
            </li>
            <li>
              This is a project-built application, not a security-audited product. Run it in an
              environment you control before using real confidential material.
            </li>
          </ul>
        </Section>

        <Section icon={BookOpen} title="11. References" id="references">
          <ul className="space-y-1.5 text-[12.5px]">
            <li>
              Reimers, N., &amp; Gurevych, I. (2019). <em>Sentence-BERT: Sentence Embeddings using
              Siamese BERT-Networks.</em> EMNLP-IJCNLP.
            </li>
            <li>
              Wang, W., Wei, F., Dong, L., Bao, H., Yang, N., &amp; Zhou, M. (2020). <em>MiniLM: Deep
              Self-Attention Distillation for Task-Agnostic Compression of Pre-Trained
              Transformers.</em> NeurIPS.
            </li>
            <li>
              Hugging Face. <em>sentence-transformers/all-MiniLM-L6-v2 model card</em>.
              <a
                className="link ml-1 inline-flex items-center gap-0.5"
                href="https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2"
                target="_blank"
                rel="noreferrer noopener"
              >
                huggingface.co <ExternalLink className="h-3 w-3" />
              </a>
            </li>
            <li>
              Potthast, M., et al. (2010–2014). <em>PAN plagiarism detection shared tasks</em> —
              background on passage-level reuse detection and evaluation practice.
            </li>
          </ul>
        </Section>
      </div>

      <div className="mt-6 flex flex-wrap gap-2 border-t border-navy-100 pt-5">
        <Link to="/analysis/new" className="btn btn-primary btn-md">
          Run a comparison
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
        <Link to="/dashboard" className="btn btn-ghost btn-md">
          Back to dashboard
        </Link>
      </div>
    </div>
  )
}
