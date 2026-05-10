"use strict";
const {
  Paragraph,TextRun,Table,TableRow,TableCell,ImageRun,
  AlignmentType,HeadingLevel,BorderStyle,WidthType,ShadingType,
  VerticalAlign,PageNumber,PageBreak,LevelFormat,TabStopType,TabStopPosition,
} = require("docx");
const fs = require("fs"), path = require("path");

const F="Times New Roman", BS=24, HS=28, CS=22, SS=20;
const C={dk:"1F3864",mb:"2E74B5",lb:"CFE2F3",wh:"FFFFFF",gy:"F2F2F2",bd:"BFBFBF",tx:"111111",rd:"C62828",gn:"2E7D32"};
const CW=11906,CH=16838,MG=1440,CNTW=CW-MG*2;
const DIAG=path.join(__dirname,"diagrams");

function br(){return new Paragraph({border:{bottom:{style:BorderStyle.SINGLE,size:8,color:C.mb,space:1}},spacing:{before:120,after:120},children:[]});}
function pb(){return new Paragraph({children:[new PageBreak()]});}
function sp(b=80,a=80){return new Paragraph({spacing:{before:b,after:a},children:[]});}

function p(text,opts={}){
  const runs=[];
  if(Array.isArray(text)){
    text.forEach(seg=>{
      if(typeof seg==="string") runs.push(new TextRun({text:seg,font:F,size:BS}));
      else runs.push(new TextRun({text:seg.t,font:F,size:BS,bold:!!seg.b,italics:!!seg.i,color:seg.c||C.tx}));
    });
  } else {
    runs.push(new TextRun({text,font:F,size:BS,bold:!!opts.bold,italics:!!opts.italic}));
  }
  return new Paragraph({
    alignment:opts.j?AlignmentType.JUSTIFIED:opts.c?AlignmentType.CENTER:AlignmentType.LEFT,
    spacing:{before:opts.sb||80,after:opts.sa||80},
    indent:opts.hang?{left:720,hanging:720}:undefined,
    children:runs,
  });
}

function ps(arr,opts={}){return arr.map(t=>p(t,{j:true,...opts}));}

function h1(text,id){
  const run=new TextRun({text,font:F,size:HS,bold:true,color:C.dk});
  return new Paragraph({
    heading:HeadingLevel.HEADING_1,spacing:{before:360,after:160},
    children:id?[Object.assign(run,{})]:[ run ],
  });
}
function h2(text){
  return new Paragraph({
    heading:HeadingLevel.HEADING_2,spacing:{before:240,after:120},
    children:[new TextRun({text,font:F,size:HS,bold:true,color:C.mb})],
  });
}
function h3(text){
  return new Paragraph({
    heading:HeadingLevel.HEADING_3,spacing:{before:180,after:80},
    children:[new TextRun({text,font:F,size:HS,bold:true,color:C.tx})],
  });
}

function figCap(label,text){
  return new Paragraph({
    alignment:AlignmentType.CENTER,spacing:{before:60,after:160},
    children:[new TextRun({text:`${label}: ${text}`,font:F,size:CS,italics:true,color:"444444"})],
  });
}
function tblCap(label,text){
  return new Paragraph({
    alignment:AlignmentType.CENTER,spacing:{before:160,after:60},
    children:[new TextRun({text:`${label}: ${text}`,font:F,size:CS,italics:true,color:"444444"})],
  });
}

function bullet(text,lvl=0){
  return new Paragraph({
    numbering:{reference:"bullets",level:lvl},
    spacing:{before:60,after:60},
    children:[new TextRun({text,font:F,size:BS})],
  });
}
function bullets(arr,lvl=0){return arr.map(t=>bullet(t,lvl));}

function mkCell(text,opts={}){
  const isH=opts.h||false;
  return new TableCell({
    width:opts.w?{size:opts.w,type:WidthType.DXA}:undefined,
    shading:{fill:opts.fill||(isH?C.dk:C.wh),type:ShadingType.CLEAR},
    verticalAlign:VerticalAlign.CENTER,
    margins:{top:80,bottom:80,left:120,right:120},
    borders:{top:{style:BorderStyle.SINGLE,size:4,color:C.bd},bottom:{style:BorderStyle.SINGLE,size:4,color:C.bd},left:{style:BorderStyle.SINGLE,size:4,color:C.bd},right:{style:BorderStyle.SINGLE,size:4,color:C.bd}},
    children:[new Paragraph({
      alignment:opts.c?AlignmentType.CENTER:AlignmentType.LEFT,
      children:[new TextRun({text,font:F,size:SS,bold:isH||opts.bold||false,color:isH?C.wh:C.tx})],
    })],
  });
}

function altCell(text,ri,opts={}){
  return new TableCell({
    width:opts.w?{size:opts.w,type:WidthType.DXA}:undefined,
    shading:{fill:ri%2===0?C.wh:"EAF2FB",type:ShadingType.CLEAR},
    verticalAlign:VerticalAlign.CENTER,
    margins:{top:80,bottom:80,left:120,right:120},
    borders:{top:{style:BorderStyle.SINGLE,size:4,color:C.bd},bottom:{style:BorderStyle.SINGLE,size:4,color:C.bd},left:{style:BorderStyle.SINGLE,size:4,color:C.bd},right:{style:BorderStyle.SINGLE,size:4,color:C.bd}},
    children:[new Paragraph({
      alignment:opts.c?AlignmentType.CENTER:AlignmentType.LEFT,
      children:[new TextRun({text,font:F,size:SS,bold:!!opts.bold,color:C.tx})],
    })],
  });
}

function mkTable(headers,rows,colWidths){
  return new Table({
    width:{size:CNTW,type:WidthType.DXA},
    columnWidths:colWidths,
    rows:[
      new TableRow({tableHeader:true,children:headers.map((h,i)=>mkCell(h,{h:true,w:colWidths[i],c:true}))}),
      ...rows.map((row,ri)=>new TableRow({children:row.map((v,ci)=>altCell(v,ri,{w:colWidths[ci],c:ci>0}))})),
    ],
  });
}

function img(filename,wPx,hPx){
  const fp=path.join(DIAG,filename);
  if(!fs.existsSync(fp)){console.warn("Missing:",fp);return sp();}
  const data=fs.readFileSync(fp);
  const ext=path.extname(filename).replace(".","").toLowerCase();
  const EMU=9144; // 1px≈9144 EMU at 96dpi
  return new Paragraph({
    alignment:AlignmentType.CENTER,
    spacing:{before:80,after:60},
    children:[new ImageRun({type:ext,data,transformation:{width:wPx,height:hPx},altText:{title:filename,description:filename,name:filename}})],
  });
}

module.exports={F,BS,HS,CS,SS,C,CNTW,MG,PAGE_W:CW,PAGE_H:CH,DIAG,
  br,pb,sp,p,ps,h1,h2,h3,figCap,tblCap,bullet,bullets,mkCell,altCell,mkTable,img,
  TabStopType,TabStopPosition,PageNumber,PageBreak,LevelFormat,AlignmentType,HeadingLevel,
  Paragraph,TextRun,Table,TableRow,TableCell,ImageRun,BorderStyle,WidthType,ShadingType,VerticalAlign,
};
