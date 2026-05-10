"""generate_diagrams.py — Creates all report figures as high-res PNGs."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagrams")
os.makedirs(OUT, exist_ok=True)

DB="#1F3864"; MB="#2E74B5"; LB="#CFE2F3"; AC="#E8A020"
GR="#2E7D32"; RD="#C62828"; GY="#F2F2F2"; WH="#FFFFFF"

def save(name):
    plt.savefig(os.path.join(OUT,name),dpi=180,bbox_inches="tight",facecolor=WH)
    plt.close(); print("  saved:",name)

def arr(ax,x1,y1,x2,y2,c=MB):
    ax.annotate("",xy=(x2,y2),xytext=(x1,y1),
                arrowprops=dict(arrowstyle="-|>",color=c,lw=1.8,mutation_scale=14))

def rbox(ax,x,y,w,h,fc,text,fs=10,tc=WH,sub=None,sfs=8.5):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.1",
                 facecolor=fc,edgecolor=DB,linewidth=1.4))
    ty=y+h/2+(0.17 if sub else 0)
    ax.text(x+w/2,ty,text,ha="center",va="center",fontsize=fs,
            fontweight="bold",color=tc,fontfamily="DejaVu Serif")
    if sub:
        ax.text(x+w/2,y+h/2-0.22,sub,ha="center",va="center",fontsize=sfs,
                color=tc,alpha=0.9,fontfamily="DejaVu Serif",style="italic")

def diamond(ax,cx,cy,hw,hh,fc,text,fs=9):
    xs=[cx,cx+hw,cx,cx-hw,cx]; ys=[cy+hh,cy,cy-hh,cy,cy+hh]
    ax.fill(xs,ys,facecolor=fc,edgecolor=DB,linewidth=1.3,zorder=3)
    ax.text(cx,cy,text,ha="center",va="center",fontsize=fs,
            fontweight="bold",color=WH,fontfamily="DejaVu Serif",zorder=4)

# ── Fig 3.1 Pipeline ──────────────────────────────────────────
def fig_3_1():
    fig,ax=plt.subplots(figsize=(10,13)); ax.set_xlim(0,10); ax.set_ylim(0,13); ax.axis("off")
    layers=[
        (11.6, DB, "INPUT — Code Line / File / Git Commit", None, 12),
        (9.6,  MB, "LAYER 1 — Tiered Regex Engine",
         "rules.toml · 28 rules  |  Tier 1: ×1.0   Tier 2: ×0.70   Tier 3: ×0.40  →  weight ×0.30", 11),
        (7.6,  MB, "LAYER 2 — Dual Entropy Filter",
         "Shannon Entropy + Transition Entropy  |  TE < 2.2 → Placeholder Gate  →  weight ×0.20", 11),
        (5.6,  MB, "LAYER 3 — Contextual Embedding Classifier",
         "all-MiniLM-L6-v2 (384-dim) → LogisticRegression  |  String literals only  →  weight ×0.35", 11),
        (3.6,  MB, "LAYER 4 — False Positive Suppressor",
         "14 rule-based checks (Saha et al.)  |  Penalty ≥ 0.80 → Multiplicative VETO  →  weight ×0.15", 11),
        (2.1, LB, "Combined Score  =  (L1×0.30) + (L2×0.20) + (L3×0.35) + (L4×0.15)", None, 10.5),
        (0.7,  DB, "OUTPUT — Score + Severity Label + Human-readable Explanation", None, 11),
    ]
    tc_map={DB:WH, MB:WH, LB:DB}
    for yl,fc,txt,sub,fs in layers:
        h=0.85 if sub is None else 1.5
        rbox(ax,1.0,yl,8,h,fc,txt,fs=fs,tc=tc_map[fc],sub=sub)
    for y_from,y_to in [(11.6,11.1),(9.6,9.1),(7.6,7.1),(5.6,5.1),(3.6,3.05),(2.1,1.6)]:
        arr(ax,5,y_from,5,y_to)
    # severity
    for i,(lbl,col) in enumerate([("CRITICAL ≥0.70",RD),("HIGH ≥0.50","#E65100"),
                                   ("MEDIUM ≥0.30",AC),("LOW < 0.30",GY)]):
        y_=10.8-i*0.7
        ax.add_patch(FancyBboxPatch((9.15,y_-0.2),0.8,0.38,
                     boxstyle="round,pad=0.05",facecolor=col,edgecolor="none"))
        ax.text(9.55,y_-0.01,lbl,ha="center",va="center",fontsize=7,
                fontweight="bold",color=WH if col!=GY else DB)
    ax.set_title("Fig 3.1  TriFusion Four-Layer Detection Pipeline",
                 fontsize=13,fontweight="bold",color=DB,fontfamily="DejaVu Serif",pad=10)
    save("fig_3_1_pipeline.png")

# ── Fig 3.3 Entropy Flow ───────────────────────────────────────
def fig_3_3():
    fig,ax=plt.subplots(figsize=(12,8)); ax.set_xlim(0,12); ax.set_ylim(0,8); ax.axis("off")
    rbox(ax,3.5,6.9,5,0.8,DB,"Candidate Secret String (≥8 chars)",fs=11)
    arr(ax,6,6.9,3.2,6.1); arr(ax,6,6.9,8.8,6.1)
    # Left — Shannon
    rbox(ax,1.0,4.9,4.4,1.1,MB,"Shannon Entropy  H(X)",sub="H = −Σ p·log₂(p)  |  char frequency")
    rbox(ax,1.0,3.5,4.4,1.1,LB,"your-api-key-here → H=3.29 (HIGH)\nBut word-char transitions are predictable",
         tc=DB,fs=8.5)
    # Right — Transition
    rbox(ax,6.6,4.9,4.4,1.1,DB,"Transition Entropy  TE(X)",sub="TE = −Σ p(bigram)·log₂(p(bigram))")
    rbox(ax,6.6,3.5,4.4,1.1,LB,"your-api-key-here → TE=1.84 (LOW)\n→ Placeholder correctly identified",tc=DB,fs=8.5)
    ax.text(2.8,6.07,"Shannon",ha="center",fontsize=8.5,color=MB)
    ax.text(9.2,6.07,"Transition",ha="center",fontsize=8.5,color=DB)
    arr(ax,3.2,3.5,4.5,2.3); arr(ax,8.8,3.5,7.5,2.3)
    diamond(ax,6,1.9,1.6,0.62,MB,"TE < 2.2 or\nKnown Placeholder?",fs=8.5)
    arr(ax,6,1.28,6,0.7); arr(ax,7.6,1.9,9.5,1.9,c=RD); arr(ax,4.4,1.9,2.5,1.9,c=GR)
    rbox(ax,9.5,1.4,2.3,1.0,RD,"score × 0.10",sub="90% penalty")
    rbox(ax,0.2,1.4,2.3,1.0,GR,"score = TE/4.0",sub="normalised")
    ax.text(8.35,2.05,"YES→",color=RD,fontsize=9,fontweight="bold")
    ax.text(2.95,2.05,"←NO",color=GR,fontsize=9,fontweight="bold")
    rbox(ax,2.5,0.05,7,0.78,DB,"Layer 2 Score [0.0–1.0]  →  contributes ×0.20 to Detection Score",fs=10)
    ax.set_title("Fig 3.3  Layer 2 — Dual Entropy Evaluation Flow",
                 fontsize=13,fontweight="bold",color=DB,fontfamily="DejaVu Serif",pad=10)
    save("fig_3_3_entropy.png")

# ── Fig 3.4 Classifier ────────────────────────────────────────
def fig_3_4():
    fig,ax=plt.subplots(figsize=(11,9)); ax.set_xlim(0,11); ax.set_ylim(0,9); ax.axis("off")
    rbox(ax,2.5,8.0,6,0.8,DB,"Source Code — Enclosing Method Block",fs=11)
    arr(ax,5.5,8.0,5.5,7.3)
    rbox(ax,1.5,6.1,8,1.1,MB,"String Literal Extractor",
         sub='Extracts: ["https://api.stripe.com","Bearer","sk_live_..."]  (variable names ignored)')
    # callout
    ax.add_patch(FancyBboxPatch((9.65,6.2),1.25,0.9,boxstyle="round,pad=0.08",
                 facecolor=LB,edgecolor=MB,linewidth=1))
    ax.text(10.28,6.65,"Obfuscation\nresilient:\nvar names\nNOT embedded",
            ha="center",va="center",fontsize=7,color=DB,fontfamily="DejaVu Serif")
    arr(ax,5.5,6.1,5.5,5.35)
    rbox(ax,1.5,4.25,8,1.0,"#1565C0","Sentence Transformer: all-MiniLM-L6-v2",
         sub="384-dim normalised embedding  |  runs locally, no API calls, ~80 MB")
    arr(ax,5.5,4.25,5.5,3.5)
    rbox(ax,1.5,2.6,8,0.85,MB,"LogisticRegression Classifier",
         sub="Trained on 82 examples  |  CV F1 = 0.906 ± 0.116  (StratifiedKFold k=5)")
    arr(ax,5.5,2.6,3.5,1.8); arr(ax,5.5,2.6,7.5,1.8)
    rbox(ax,0.5,0.8,3,0.95,GR,"P ≥ 0.55 → SECRET",sub="Reported with explanation")
    rbox(ax,7.0,0.8,3,0.95,RD,"P < 0.55 → NOT SECRET",sub="Suppressed silently")
    ax.text(3.1,1.76,"≥0.55",color=GR,fontsize=9,fontweight="bold",ha="center")
    ax.text(7.9,1.76,"<0.55",color=RD,fontsize=9,fontweight="bold",ha="center")
    # obfuscation table
    ax.text(0.1,5.9,"Obfuscation Test",fontsize=8.5,fontweight="bold",color=DB)
    hdr=["","Normal","Obfusc."]
    rows=[["Var names","api_key","a,b,c"],["Str lits","preserved","preserved"],
          ["Score","0.907","0.893"],["Delta","—","0.014"]]
    cw=[0.85,0.85,0.75]; th=0.32; tx=0.1; ty=4.45
    for ci,h in enumerate(hdr):
        cx=tx+sum(cw[:ci])
        ax.add_patch(FancyBboxPatch((cx,ty+len(rows)*th),cw[ci],th,
                     boxstyle="square,pad=0",facecolor=DB,edgecolor=WH,linewidth=0.5))
        ax.text(cx+cw[ci]/2,ty+len(rows)*th+th/2,h,ha="center",va="center",
                fontsize=7,fontweight="bold",color=WH)
    for ri,row in enumerate(rows):
        for ci,val in enumerate(row):
            cx=tx+sum(cw[:ci]); ry=ty+(len(rows)-1-ri)*th
            ax.add_patch(FancyBboxPatch((cx,ry),cw[ci],th,
                         boxstyle="square,pad=0",
                         facecolor=LB if ri%2==0 else WH,edgecolor=GY,linewidth=0.5))
            ax.text(cx+cw[ci]/2,ry+th/2,val,ha="center",va="center",fontsize=6.8,color="#111")
    ax.set_title("Fig 3.4  Layer 3 — Contextual Embedding Classifier Architecture",
                 fontsize=13,fontweight="bold",color=DB,fontfamily="DejaVu Serif",pad=10)
    save("fig_3_4_classifier.png")

# ── Fig 3.6 FP Suppressor Gate ───────────────────────────────
def fig_3_6():
    fig,ax=plt.subplots(figsize=(13,10)); ax.set_xlim(0,13); ax.set_ylim(0,10); ax.axis("off")
    rbox(ax,4.5,9.2,4,0.7,DB,"Candidate from Layers 1–3",fs=10.5)
    arr(ax,6.5,9.2,6.5,8.65)
    rules=[
        (3.0,8.2,"Function call?\npassword=getFunc()","0.95",MB),
        (10.0,8.2,"Variable assign?\nkey=os.environ[…]","0.90",DB),
        (3.0,6.5,"Test directory?\n/tests/ /mocks/","0.85",MB),
        (10.0,6.5,"README / docs?\n.md .rst .txt","0.85",DB),
        (3.0,4.8,"Placeholder?\nyour-key-here","0.90",MB),
        (10.0,4.8,"Weak password?\nadmin root password","0.85",DB),
    ]
    arr(ax,6.5,8.65,3.0,8.2+0.55); arr(ax,6.5,8.65,10.0,8.2+0.55)
    for i,(cx,cy,txt,pen,fc) in enumerate(rules):
        diamond(ax,cx,cy,1.4,0.58,fc,txt,fs=8)
        ax.annotate("",xy=(cx+2.0,cy),xytext=(cx+1.4,cy),
                    arrowprops=dict(arrowstyle="-|>",color=RD,lw=1.5,mutation_scale=12))
        ax.text(cx+2.1,cy+0.08,f"YES +{pen}",color=RD,fontsize=8,fontweight="bold")
        if i in(0,1): arr(ax,cx,cy-0.58,cx,6.5+0.58)
        if i in(2,3): arr(ax,cx,cy-0.58,cx,4.8+0.58)
    ax.text(6.3,4.1,"+ 8 more rules (numeric, CSS, null, empty,\ncommented, repeated chars, no-cloud-API)",
            ha="center",fontsize=8.5,color=DB,style="italic",
            bbox=dict(boxstyle="round,pad=0.3",fc=LB,ec=MB,lw=1))
    arr(ax,3.0,4.8-0.58,5.2,3.15); arr(ax,10.0,4.8-0.58,7.8,3.15); arr(ax,6.5,4.0,6.5,3.65)
    diamond(ax,6.5,3.1,1.9,0.68,AC,"Total Penalty\n≥ 0.80?",fs=10)
    arr(ax,6.5,2.42,6.5,1.8,c=RD)
    ax.text(6.75,2.1,"YES",color=RD,fontsize=10,fontweight="bold")
    rbox(ax,4.1,0.85,4.8,0.87,RD,"MULTIPLICATIVE GATE — VETO",
         sub="base_score × suppressor_score ≈ 0  →  Not Reported")
    arr(ax,8.4,3.1,10.5,3.1,c=GR)
    ax.text(8.85,3.25,"NO",color=GR,fontsize=10,fontweight="bold")
    rbox(ax,10.5,2.55,2.4,1.05,GR,"ADDITIVE",sub="score + supp×0.15\n→ Reported")
    ax.set_title("Fig 3.6  Layer 4 — False Positive Suppressor Decision Gate",
                 fontsize=13,fontweight="bold",color=DB,fontfamily="DejaVu Serif",pad=10)
    save("fig_3_6_suppressor.png")

# ── Fig 4.1 Ablation bar chart ────────────────────────────────
def fig_4_1():
    configs=["L1 Only\n(Regex)","L1+L2\n(+Entropy)","L1+L3\n(+Classifier)",
             "L1+L4\n(+FP Supp.)","TriFusion\nFull"]
    prec=[0.473,0.473,0.473,1.000,1.000]
    rec =[0.867,0.867,0.867,0.867,0.867]
    f1  =[0.612,0.612,0.612,0.929,0.929]
    fpr =[0.644,0.644,0.644,0.000,0.000]
    x=np.arange(len(configs)); w=0.19
    fig,ax=plt.subplots(figsize=(13,6.5)); fig.patch.set_facecolor(WH); ax.set_facecolor(WH)
    b1=ax.bar(x-1.5*w,prec,w,label="Precision",color=DB,edgecolor=WH)
    b2=ax.bar(x-0.5*w,rec, w,label="Recall",   color=MB,edgecolor=WH)
    b3=ax.bar(x+0.5*w,f1,  w,label="F1 Score", color="#5BA3D0",edgecolor=WH)
    b4=ax.bar(x+1.5*w,fpr, w,label="FPR",      color=RD,edgecolor=WH,alpha=0.8)
    ax.axvspan(3.55,4.45,alpha=0.07,color=AC,zorder=0)
    ax.text(4.0,1.04,"★ Best Precision & F1",ha="center",fontsize=9.5,color=AC,fontweight="bold")
    for bars in [b1,b2,b3,b4]:
        for bar in bars:
            v=bar.get_height()
            if v>0:
                ax.text(bar.get_x()+bar.get_width()/2,v+0.01,f"{v:.3f}",
                        ha="center",va="bottom",fontsize=7,color="#111",fontfamily="DejaVu Serif")
    ax.set_ylim(0,1.12); ax.set_xticks(x); ax.set_xticklabels(configs,fontsize=10)
    ax.set_ylabel("Score",fontsize=11); ax.yaxis.grid(True,linestyle="--",alpha=0.4)
    ax.set_axisbelow(True)
    for s in ["top","right"]: ax.spines[s].set_visible(False)
    ax.legend(fontsize=10,framealpha=0.9,loc="upper left")
    ax.set_title("Fig 4.1  Ablation Study — Layer-by-Layer Contribution (75-Scenario Benchmark)",
                 fontsize=13,fontweight="bold",color=DB,fontfamily="DejaVu Serif",pad=12)
    plt.tight_layout(); save("fig_4_1_ablation.png")

# ── Fig 4.2 Industry benchmark ────────────────────────────────
def fig_4_2():
    tools=["TruffleHog v3","Gitleaks v8","SpotBugs","PassFinder","TriFusion (Ours)"]
    prec=[0.280,0.350,0.670,0.510,1.000]
    rec =[0.920,0.880,0.410,0.740,0.867]
    f1  =[0.430,0.500,0.510,0.600,0.929]
    y=np.arange(len(tools)); h=0.22
    fig,ax=plt.subplots(figsize=(11,6)); fig.patch.set_facecolor(WH); ax.set_facecolor(WH)
    b1=ax.barh(y+h, prec,h,label="Precision",color=DB,edgecolor=WH)
    b2=ax.barh(y,   rec, h,label="Recall",   color=MB,edgecolor=WH)
    b3=ax.barh(y-h, f1,  h,label="F1 Score", color="#5BA3D0",edgecolor=WH)
    ax.axhspan(3.55,4.45,alpha=0.09,color=AC,zorder=0)
    for bars in [b1,b2,b3]:
        for bar in bars:
            v=bar.get_width()
            ax.text(v+0.007,bar.get_y()+bar.get_height()/2,f"{v:.3f}",
                    va="center",ha="left",fontsize=8.5,color="#111")
    ax.text(1.01,4.05,"FPR = 0.000  ★",va="center",ha="left",
            fontsize=9.5,color=AC,fontweight="bold")
    ax.set_xlim(0,1.22); ax.set_yticks(y); ax.set_yticklabels(tools,fontsize=11)
    ax.set_xlabel("Score",fontsize=11); ax.xaxis.grid(True,linestyle="--",alpha=0.4)
    ax.set_axisbelow(True)
    for s in ["top","right"]: ax.spines[s].set_visible(False)
    ax.legend(fontsize=10.5,framealpha=0.9,loc="lower right")
    ax.set_title("Fig 4.2  Industry Benchmark Comparison — Precision, Recall, F1 Score",
                 fontsize=13,fontweight="bold",color=DB,fontfamily="DejaVu Serif",pad=12)
    plt.tight_layout(); save("fig_4_2_benchmark.png")

if __name__=="__main__":
    print("Generating diagrams...")
    fig_3_1(); fig_3_3(); fig_3_4(); fig_3_6(); fig_4_1(); fig_4_2()
    print("All done →",OUT)
