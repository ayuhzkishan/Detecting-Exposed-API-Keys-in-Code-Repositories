"use strict";
const {Document,Packer,Header,Footer,Paragraph,TextRun,PageNumber,
  AlignmentType,BorderStyle,TabStopType,TabStopPosition,LevelFormat,
  TableOfContents,
}=require("docx");
const fs=require("fs"),path=require("path");
const H=require("./rpt_helpers");
const {cover,toc,listOfFigures,listOfAbbr}=require("./rpt_cover");
const {ch1,ch2}=require("./rpt_ch1ch2");
const {ch3}=require("./rpt_ch3");
const {ch4,ch5,refs}=require("./rpt_ch4ch5");

// ── Abstract (inline, short) ───────────────────────────────────
function abstract(){
  return[
    H.h1("Abstract"),
    ...H.ps([
      "Accidental exposure of authentication credentials in publicly accessible code repositories constitutes a persistent and consequential security vulnerability. Despite the availability of multiple automated scanning tools, adoption remains low because high false-positive rates erode developer trust and generate alert fatigue. This report presents TriFusion, a hybrid four-layer detection framework that systematically addresses the documented failure modes of existing tools through a combination of tiered regular expression matching, dual entropy analysis, obfuscation-resilient contextual embedding classification, and a rule-based false positive suppressor grounded in published empirical research.",
      "On a 75-scenario benchmark covering the complete Saha et al. false positive taxonomy, TriFusion achieves a Precision of 1.000, a Recall of 0.867, an F1 score of 0.929, and a False Positive Rate of 0.000 — outperforming all compared tools on the precision and F1 axes. The system is delivered as an installable Python package with a full command-line interface, pre-commit hook integration, git history scanning, and a reproducible research benchmark suite.",
    ],{j:true}),
    new Paragraph({
      spacing:{before:80,after:80},
      children:[
        new TextRun({text:"Keywords: ",font:H.F,size:H.BS,bold:true}),
        new TextRun({text:"API key detection, secret scanning, false positive suppression, transition entropy, contextual embeddings, DevSecOps, pre-commit hooks, obfuscation resilience",font:H.F,size:H.BS,italics:true}),
      ],
    }),
    H.pb(),
  ];
}

// ── Document ──────────────────────────────────────────────────
const doc=new Document({
  styles:{
    default:{document:{run:{font:H.F,size:H.BS}}},
    paragraphStyles:[
      {id:"Heading1",name:"Heading 1",basedOn:"Normal",next:"Normal",quickFormat:true,
       run:{size:H.HS,bold:true,font:H.F,color:H.C.dk},
       paragraph:{spacing:{before:360,after:160},outlineLevel:0}},
      {id:"Heading2",name:"Heading 2",basedOn:"Normal",next:"Normal",quickFormat:true,
       run:{size:H.HS,bold:true,font:H.F,color:H.C.mb},
       paragraph:{spacing:{before:240,after:120},outlineLevel:1}},
      {id:"Heading3",name:"Heading 3",basedOn:"Normal",next:"Normal",quickFormat:true,
       run:{size:H.HS,bold:true,font:H.F,color:H.C.tx},
       paragraph:{spacing:{before:180,after:80},outlineLevel:2}},
    ],
  },
  numbering:{config:[{
    reference:"bullets",
    levels:[
      {level:0,format:LevelFormat.BULLET,text:"\u2022",alignment:AlignmentType.LEFT,
       style:{paragraph:{indent:{left:720,hanging:360}}}},
      {level:1,format:LevelFormat.BULLET,text:"\u25E6",alignment:AlignmentType.LEFT,
       style:{paragraph:{indent:{left:1080,hanging:360}}}},
    ],
  }]},
  sections:[{
    properties:{page:{
      size:{width:H.PAGE_W,height:H.PAGE_H},
      margin:{top:H.MG,right:H.MG,bottom:H.MG,left:H.MG},
    }},
    headers:{default:new Header({children:[new Paragraph({
      border:{bottom:{style:BorderStyle.SINGLE,size:6,color:H.C.mb,space:1}},
      tabStops:[{type:TabStopType.RIGHT,position:TabStopPosition.MAX}],
      children:[
        new TextRun({text:"TriFusion — Detecting Exposed API Keys in Code Repositories",font:H.F,size:H.SS,color:H.C.mb}),
        new TextRun({text:"\tAyush Kishan  |  2025-2026",font:H.F,size:H.SS,color:"888888"}),
      ],
    })]})},
    footers:{default:new Footer({children:[new Paragraph({
      border:{top:{style:BorderStyle.SINGLE,size:6,color:H.C.mb,space:1}},
      alignment:AlignmentType.CENTER,
      children:[
        new TextRun({text:"Page ",font:H.F,size:H.SS,color:"888888"}),
        new TextRun({children:[PageNumber.CURRENT],font:H.F,size:H.SS,color:"888888"}),
        new TextRun({text:" of ",font:H.F,size:H.SS,color:"888888"}),
        new TextRun({children:[PageNumber.TOTAL_PAGES],font:H.F,size:H.SS,color:"888888"}),
      ],
    })]})},
    children:[
      ...cover(),
      ...toc(),
      ...abstract(),
      ...listOfFigures(),
      ...listOfAbbr(),
      ...ch1(),
      ...ch2(),
      ...ch3(),
      ...ch4(),
      ...ch5(),
      ...refs(),
    ],
  }],
});

const OUT=path.join(__dirname,"TriFusion_Project_Report.docx");
Packer.toBuffer(doc).then(buf=>{
  fs.writeFileSync(OUT,buf);
  console.log("Report written:",OUT,"("+Math.round(buf.length/1024)+" KB)");
}).catch(e=>{console.error(e);process.exit(1);});
