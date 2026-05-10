"use strict";
const {h1,h2,h3,p,ps,bullets,mkTable,tblCap,br,pb,sp,F,BS,C}=require("./rpt_helpers");

function ch1(){
  return[
    h1("1. Introduction"),
    ...ps([
      "Cloud-native software development has become deeply reliant on third-party services: payment gateways, object storage, messaging platforms, and identity providers all authenticate via API keys or tokens. These credentials are typically short strings that, once known to an adversary, grant unrestricted programmatic access to the associated resource. The practical reality of fast-paced development cycles is that such credentials are routinely embedded directly into source code during prototyping and, critically, forgotten before the code is committed to a version-controlled repository.",
      "Public hosting platforms receive millions of new commits every day. Automated crawlers index these commits within seconds of publication, and credential-harvesting bots operate continuously across the most popular platforms. Once a key is captured, it may be used to provision cloud compute for cryptocurrency mining, exfiltrate stored data, or pivot into connected internal systems. The damage is rarely contained to a single service: compromised OAuth tokens frequently grant access to entire organisational identity graphs, and AWS keys with broad IAM permissions can give an attacker root-equivalent access to all deployed infrastructure.",
      "Existing detection tooling addresses this problem incompletely. Rule-based scanners such as Gitleaks and TruffleHog achieve high recall by casting wide regex nets, but the consequence is a false-positive rate that exceeds 60% on real-world codebases. Alert fatigue is a documented and serious outcome: when developers receive dozens of spurious warnings per scan, they systematically disable scanners or build suppression lists that inadvertently exclude genuine leaks. Machine-learning approaches such as PassFinder improve precision but introduce a different fragility — their classifiers embed variable names as context signals, and those names are erased by standard code obfuscation.",
    ],{j:true}),

    h2("1.1 Motivation"),
    ...ps([
      "The core motivation for TriFusion arises from three empirical observations drawn from published benchmark studies. First, Basak et al. demonstrated that no existing tool achieves both high precision and high recall simultaneously: the tools with the highest recall (TruffleHog, 92%) also exhibit the lowest precision (28%), while tools with moderate precision (SpotBugs, 67%) sacrifice recall dramatically (41%). This precision-recall trade-off has remained essentially unchanged across three generations of tooling.",
      "Second, Saha et al. catalogued nine distinct categories of false positive that account for the overwhelming majority of erroneous detections. These categories — function call returns, variable-to-variable assignments, placeholder strings, commented code, test fixtures, null assignments, documentation files, CSS values, and numeric constants — are well-understood patterns that are entirely amenable to deterministic rule-based suppression. No publicly available tool implements all nine, which means the precision ceiling for existing tools is artificially constrained.",
      "Third, Li et al. showed that even well-designed ML classifiers fail when source code is obfuscated. Android APK reverse-engineering studies confirmed that obfuscation reliably destroys all identifier-based context while leaving string literals — URLs, format strings, error messages — fully intact. A classifier that embeds only string literals is therefore obfuscation-resilient by design.",
      "TriFusion combines these three insights into a single integrated pipeline, with each layer targeting a documented gap rather than a theoretical concern.",
    ],{j:true}),

    h2("1.2 Objectives"),
    ...bullets([
      "Construct a tiered regex engine that differentiates high-confidence platform-specific patterns from lower-confidence generic patterns, and assigns a numerical weight to each tier.",
      "Implement a dual entropy gate that combines Shannon and Transition entropy to reject both repetitive placeholders and semantically obvious non-secrets without human intervention.",
      "Train an obfuscation-resilient contextual classifier by embedding only the string literals present in the enclosing function body, using a lightweight sentence-transformer model that runs locally without API calls.",
      "Derive and implement a 14-rule false positive suppressor whose rules map one-to-one onto the empirically documented FP taxonomy from Saha et al. and the weak-password findings from Cabasa et al.",
      "Produce a combined detection score with four weighted components and generate a human-readable explanation for every flagged or suppressed finding.",
      "Achieve a False Positive Rate of zero and an F1 score above 0.90 on a 75-scenario labelled benchmark covering the complete published FP taxonomy.",
      "Deliver the system as an installable Python package with a full CLI, pre-commit hook support, git history scanning, and a reproducible research benchmark suite.",
    ]),
    pb(),
  ];
}

function ch2(){
  const litRows=[
    ["Basak et al., 2022","SecretBench, MSR","Benchmarked 11 tools; TruffleHog precision=0.28, Gitleaks=0.35. No tool exceeds 67% precision."],
    ["Saha et al., 2022","SecretsHunter, ASE","Identified 9 FP categories (D1–D9). Regex alone peaks at 84% precision."],
    ["Li et al., 2023","PassFinder, ICSE","ML classifier using variable names; fails under APK obfuscation."],
    ["Cabasa et al., 2023","SIGCSE","Student repos dominated by weak defaults: admin, root, devpassword."],
    ["Meli et al., 2019","NDSS","Secrets indexed within 4 seconds of GitHub push by automated crawlers."],
    ["GitGuardian, 2021","Industry Report","6M+ credentials leaked on GitHub in one calendar year."],
  ];
  return[
    h1("2. Literature Review"),
    ...ps([
      "Credential leakage research has accelerated since 2019, when Meli et al. demonstrated that automated bots routinely harvest newly pushed secrets within four seconds of a public commit. That discovery reframed the problem from one of eventual discovery to one of near-immediate exploitation, making preventive detection at commit time the only practically viable defence. The research community has since produced two broad streams of work: empirical benchmarking studies that characterise the failure modes of existing tools, and system-building studies that propose improved detectors.",
    ],{j:true}),

    h2("2.1 Empirical Benchmarking"),
    ...ps([
      "SecretBench (Basak et al., MSR 2022) remains the most comprehensive evaluation of secret detection tools to date. The authors curated 818 confirmed real secrets and 1,450 confirmed non-secrets across 97,479 public repositories and evaluated eleven tools against this ground truth. The headline finding is that the tool space partitions cleanly into two clusters: recall-optimised tools with precision around 30–35%, and precision-optimised tools with recall below 50%. No tool occupies the high-precision, high-recall quadrant. SecretBench also introduced the secret category taxonomy — Tier-A platform-specific prefixed keys, Tier-B keyword-anchored assignments, and Tier-C obfuscated or indirect references — that forms the basis of the TriFusion benchmark design.",
      "SecretsHunter (Saha et al., ASE 2022) focuses specifically on understanding why regex-based tools produce false positives. Through manual inspection of 2,000 erroneous detections from three production tools, the authors identify nine recurring FP patterns, each of which represents a distinct semantic context in which a regex match is structurally valid but semantically meaningless as a credential. This taxonomy is foundational to TriFusion's Layer 4 design: each of the 14 suppression rules in fp_suppressor.py maps directly onto one of these documented patterns.",
    ],{j:true}),

    h2("2.2 Machine Learning Approaches"),
    ...ps([
      "PassFinder (Li et al., ICSE 2023) represents the state of the art among ML-based secret detectors. It embeds the code context surrounding a candidate match — including variable names, function names, and structural tokens — into a classifier input. On standard benchmarks, PassFinder achieves precision of 0.510 and recall of 0.740, outperforming all regex-only tools on the precision axis. However, the evaluation does not include obfuscated code scenarios. A targeted experiment conducted as part of the TriFusion evaluation confirms that when variable names are replaced by single-character identifiers (a standard output of Android ProGuard obfuscation), the PassFinder classifier's discriminative signal collapses because the variable-name features that carry the most weight are destroyed.",
      "Earlier ML work by Saha et al. and by Truffles (a TruffleHog variant) used Shannon entropy thresholding as a filtering step. While effective against random-character strings, Shannon entropy is blind to semantic structure: a phrase such as \"your-api-key-here\" achieves a Shannon entropy of 3.29 bits because it contains a varied character set, yet is obviously a placeholder. TriFusion's transition entropy measure, which evaluates character-pair unpredictability rather than character frequency, correctly identifies this string as low-entropy because its character transitions follow predictable word-hyphen patterns.",
    ],{j:true}),

    h2("2.3 Industry Practice and Gaps"),
    ...ps([
      "Cabasa et al. (SIGCSE 2023) examined secret leakage in student repositories and found that the most common non-secret pattern was weak or default credentials: strings such as 'admin', 'root', 'password123', and 'devpassword'. These strings satisfy generic password-detection regexes but are not real operational credentials. No prior academic tool includes a dedicated weak-password suppression rule. TriFusion's Rule 14 addresses this gap directly, drawing on a curated list derived from the Cabasa et al. findings and the OWASP Top-10 weak password list.",
      "GitGuardian's 2021 State of Secrets Sprawl report provides industrial scale context: over six million unique credentials were identified in public GitHub commits in a single year, with an average time-to-discovery by malicious bots of under one minute. The report notes that 85% of leaked secrets remain valid for more than 24 hours after exposure, indicating that detection tools are rarely integrated into commit workflows. TriFusion's pre-commit hook integration directly targets this gap by making detection automatic and mandatory at commit time.",
    ],{j:true}),

    tblCap("Table 2.1","Summary of Key Related Works"),
    mkTable(["Author(s) & Year","Venue","Key Finding / Research Gap"],litRows,[2200,1800,5026]),
    pb(),
  ];
}

module.exports={ch1,ch2};
