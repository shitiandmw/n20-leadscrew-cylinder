"""Silhouette, actual CAD views and independent-drive dynamics evidence."""
from pathlib import Path
import gzip,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image
from shapely.geometry import LineString
from check_shape import profile
from kinematics import BOOM_PROFILE_POINTS,BOOM_PROFILE_RADII
ROOT=Path(__file__).resolve().parents[1]
font='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc';font_manager.fontManager.addfont(font)
plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name();plt.rcParams['axes.unicode_minus']=False
teal='#13818b';orange='#bc682d';ink='#203c48'
old=profile([(0,0),(72,54.4),(136,76),(184,68),(380,0)],[18,20,24,20,16]);new=profile(BOOM_PROFILE_POINTS,BOOM_PROFILE_RADII)
fig,ax=plt.subplots(figsize=(12,5.5),layout='constrained');fig.patch.set_facecolor('#f5f8f6')
x,z=new.exterior.xy;ax.fill(x,z,color='#edb33e',alpha=.8,label='R10 中段加深、两端收窄')
x,z=old.exterior.xy;ax.plot(x,z,color=ink,ls='--',lw=2,label='R9 原轮廓')
for body,color,dx,label,tx,align in [(old,ink,-5,'R9',130,'right'),(new,teal,10,'R10',164,'left')]:
 b=body.intersection(LineString([(142,-300),(142,300)])).bounds;ax.annotate('',xy=(142+dx,b[3]),xytext=(142+dx,b[1]),arrowprops=dict(arrowstyle='<->',color=color,lw=1.5));ax.text(tx,(b[1]+b[3])/2,f'{label} {b[3]-b[1]:.1f} mm',color=color,fontsize=12,va='center',ha=align,bbox=dict(facecolor='#f5f8f6',edgecolor='none',alpha=.9,pad=2))
ax.plot([0,380],[0,0],color='#84989f',ls=':',lw=1);ax.scatter([0,380],[0,0],s=45,facecolors='white',edgecolors=ink,zorder=5)
ax.text(-5,-31,'O 根部',fontsize=11);ax.text(352,-31,'E 斗杆销',fontsize=11)
ax.set_aspect('equal');ax.set(xlabel='大臂局部 X / mm',ylabel='大臂局部 Z / mm',xlim=(-35,415),ylim=(-45,145));ax.grid(alpha=.15);ax.legend(loc='upper right',fontsize=10)
ax.set_title('R10 回旋镖形箱梁：中部截面约 76.7 mm，较 R9 的 47.8 mm 更深',fontsize=15,color=ink,pad=15)
fig.get_layout_engine().set(rect=(0,.075,1,.925))
fig.text(.14,.025,'此图采用大臂自身坐标，不代表安装姿态；不含附加支座。箱体宽度 48 mm，名义壁厚 4 mm。',fontsize=10,color=ink)
fig.savefig(ROOT/'images/boom_shape_comparison.png',dpi=160,bbox_inches='tight');plt.close(fig)

fig,axes=plt.subplots(1,3,figsize=(14,6),width_ratios=[1.2,1,.55],layout='constrained');fig.patch.set_facecolor('#f5f8f6')
axes[0].imshow(Image.open(ROOT/'references/user_structure.png'));axes[0].set_title('用户参考照片 / 弯臂与厚中段',fontsize=13,color=ink)
axes[1].imshow(Image.open(ROOT/'images/oblique_preview.png').crop((575,220,1000,565)));axes[1].set_title('R10 实际 CAD / 斜视',fontsize=13,color=ink)
axes[2].imshow(Image.open(ROOT/'images/front_preview.png').crop((720,225,865,445)));axes[2].set_title('正视 / 左右两根',fontsize=13,color=ink)
for ax in axes:ax.axis('off')
fig.suptitle('双推杆 + 中部加深的回旋镖形大臂',fontsize=18,color=ink,weight='bold')
fig.get_layout_engine().set(rect=(0,.065,1,.935))
fig.text(.08,.025,'两根大臂推杆位于 Y = −50 / +50 mm；保留 380 mm 销距、88 mm 主铰点和五颗可换斗齿。照片未用于尺寸测量。',fontsize=11,color=ink)
fig.savefig(ROOT/'images/structure_reference.png',dpi=160,bbox_inches='tight');plt.close(fig)

motion=json.loads((ROOT/'motion.json').read_text());tt=np.array([f['t']*20 for f in motion['frames']]);planned=np.array([f['tip'] for f in motion['frames']])
rows=json.loads(gzip.decompress((ROOT/'simulation/payload_150g_trace.json.gz').read_bytes()))['frames'];t=np.array([f['time'] for f in rows]);tip=np.array([f['tip_mm'] for f in rows])[:,[0,2]];forces=np.array([f['force_N'] for f in rows]);actual=np.array([f['drive_strokes'] for f in rows]);target=np.array([f['target_drive_strokes'] for f in rows])
fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained');fig.patch.set_facecolor('#f5f8f6')
axes[0,0].plot(*planned.T,color=ink,ls='--',lw=2,label='目标');axes[0,0].plot(*tip.T,color=teal,lw=1,label='150 g 实际积分');axes[0,0].axhline(0,color='#8c9ca2',ls=':');axes[0,0].set(xlabel='齿尖 X / mm',ylabel='齿尖 Z / mm',title='带载实际轨迹与目标重合')
axes[0,1].plot(t,forces[:,0],color=teal,lw=2.5,label='左大臂推杆');axes[0,1].plot(t,forces[:,1],color=orange,lw=1.5,ls='--',label='右大臂推杆');axes[0,1].axhline(100,color=ink,ls=':',label='每根假设上限 100 N');axes[0,1].set(xlabel='仿真时间 / s',ylabel='每根大臂推力 / N',title='名义同步条件下，左右分担一致',ylim=(0,110))
for i,(label,color) in enumerate([('左大臂',teal),('右大臂',orange),('斗杆','#72849e'),('铲斗','#8c6b90')]):axes[1,0].plot(t,actual[:,i]-target[:,i],label=label,color=color,lw=1,ls='--' if i==1 else '-')
axes[1,0].set(xlabel='仿真时间 / s',ylabel='行程误差 / mm',title='四根推杆分别积分、分别反馈')
bias=json.loads(gzip.decompress((ROOT/'simulation/sync_bias_0p5mm_trace.json.gz').read_bytes()))['frames'];bt=np.array([f['time'] for f in bias]);bf=np.array([f['force_N'] for f in bias])
axes[1,1].plot(bt,bf[:,0],color=teal,label='左大臂');axes[1,1].plot(bt,bf[:,1],color=orange,label='右大臂（零点偏差 0.5 mm）');axes[1,1].set(xlabel='静止保持的仿真时间 / s',ylabel='每根推力 / N',title='同步零点偏差会造成分担失衡')
for ax in axes.flat:ax.grid(alpha=.15);ax.legend(fontsize=9);ax.tick_params(labelsize=9)
fig.suptitle('R10 动力学：150 g 示例负载可跟随，双推杆仍需同步控制',fontsize=16,color=ink,weight='bold');fig.savefig(ROOT/'images/simulation_results.png',dpi=160);plt.close(fig)
