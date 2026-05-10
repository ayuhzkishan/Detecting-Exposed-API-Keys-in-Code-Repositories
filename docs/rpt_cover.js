"use strict";
const {h1,h2,p,ps,bullets,mkTable,tblCap,br,pb,sp,
  Paragraph,TextRun,AlignmentType,HeadingLevel,PageNumber,PageBreak,
  TabStopType,TabStopPosition,F,BS,HS,SS,CS,C,CNTW,
  BorderStyle,WidthType,ShadingType,VerticalAlign,
  Table,TableRow,TableCell,LevelFormat,
}=require("./rpt_helpers");
const {TableOfContents}=require("docx");

function cover(){
  const tx=(t,sz,bold,color)=>new TextRun({text:t,font:F,size:sz,bold:!!bold,color:color||C.tx});
  const cp=(t,sz,bold,color,sa=80)=>new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:0,after:sa},children:[tx(t,sz,bold,color)]});
  return[
    sp(2200),
    cp("TriFusion",72,true,C.dk,60),
    cp("Detecting Exposed API Keys in Code Repositories",36,false,C.mb,200),
    br(),
    cp("A Hybrid Four-Layer Secret Detection Framework",28,false,C.mb,400),
    cp("Author: Ayush Kishan",BS,true,C.tx,80),
    cp("GitHub: ayuhzkishan/Detecting-Exposed-API-Keys-in-Code-Repositories",SS,false,C.mb,80),
    cp("Academic Year 2025–2026",BS,false,C.tx,80),
    pb(),
  ];
}

function toc(){
  return[
    h1("Table of Contents"),
    new TableOfContents("Table of Contents",{hyperlink:true,headingStyleRange:"1-3"}),
    pb(),
  ];
}

function listOfFigures(){
  const figs=[
    ["Fig 3.1","TriFusion Four-Layer Detection Pipeline"],
    ["Fig 3.2","Layer 2 — Dual Entropy Evaluation Flow"],
    ["Fig 3.3","Layer 3 — Contextual Embedding Classifier Architecture"],
    ["Fig 3.4","Layer 4 — False Positive Suppressor Decision Gate"],
    ["Fig 4.1","Ablation Study — Layer-by-Layer Contribution"],
    ["Fig 4.2","Industry Benchmark Comparison — Precision, Recall, F1"],
    ["Table 2.1","Summary of Related Works"],
    ["Table 3.1","Pipeline Layer Summary"],
    ["Table 3.2","Sample Detection Rules by Tier"],
    ["Table 3.3","FP Suppression Rules"],
    ["Table 3.4","CLI Commands Reference"],
    ["Table 4.1","Ablation Study Results"],
    ["Table 4.2","Industry Benchmark Comparison"],
  ];
  return[
    h1("List of Figures and Tables"),
    ...figs.map(([ref,desc])=>new Paragraph({
      spacing:{before:60,after:60},
      tabStops:[{type:TabStopType.RIGHT,position:8500,leader:"dot"}],
      children:[
        new TextRun({text:`${ref}  ${desc}`,font:F,size:BS}),
      ],
    })),
    pb(),
  ];
}

function listOfAbbr(){
  const rows=[
    ["API","Application Programming Interface"],
    ["ASE","Automated Software Engineering (conference)"],
    ["CLI","Command-Line Interface"],
    ["CV","Cross-Validation"],
    ["DevSecOps","Development, Security, and Operations"],
    ["EC","Elliptic Curve"],
    ["F1","Harmonic Mean of Precision and Recall"],
    ["FN","False Negative"],
    ["FP","False Positive"],
    ["FPR","False Positive Rate"],
    ["ICSE","International Conference on Software Engineering"],
    ["JSON","JavaScript Object Notation"],
    ["JWT","JSON Web Token"],
    ["L1–L4","Layers 1 through 4 of TriFusion pipeline"],
    ["LR","Logistic Regression"],
    ["ML","Machine Learning"],
    ["MWS","Marketplace Web Service (Amazon)"],
    ["NLP","Natural Language Processing"],
    ["OWASP","Open Web Application Security Project"],
    ["PGP","Pretty Good Privacy"],
    ["PKL","Python Pickle — serialised model format"],
    ["RSA","Rivest–Shamir–Adleman cryptographic algorithm"],
    ["SHA","Secure Hash Algorithm"],
    ["SSH","Secure Shell protocol"],
    ["TE","Transition Entropy"],
    ["TN","True Negative"],
    ["TP","True Positive"],
    ["TOML","Tom's Obvious Minimal Language"],
    ["URL","Uniform Resource Locator"],
  ];
  return[
    h1("List of Abbreviations"),
    tblCap("Table 0.1","Abbreviations Used in This Report"),
    mkTable(["Abbreviation","Full Form"],rows,[2200,6826]),
    pb(),
  ];
}

module.exports={cover,toc,listOfFigures,listOfAbbr};
