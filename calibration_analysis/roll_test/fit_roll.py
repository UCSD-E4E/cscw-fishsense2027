"""T8, robust: view screening + 2-iteration point-level outlier refit, both distortion sources."""
import sys, json, numpy as np, cv2
from pathlib import Path
SP = Path(__file__).resolve().parent; P4 = Path(__file__).resolve().parents[3] / "wuwnet-fishsense2026"; sys.path.insert(0, str(P4))
from fishsense_wuwnet.dataset import load_corner_cache, cache_by_session, board_object_points, SQUARE_PITCH_M, SQUARE_SIZE_M
SENSOR=(4014,3016); GUESS=np.array([[2900.,0,2007],[0,2900.,1508],[0,0,1]])
FIX=(cv2.CALIB_USE_INTRINSIC_GUESS|cv2.CALIB_FIX_K1|cv2.CALIB_FIX_K2|cv2.CALIB_FIX_K3|cv2.CALIB_FIX_TANGENT_DIST)
VIEW_MAX_PX = 10.0; ITERS = 2; KSIG = 3.0
rng = np.random.default_rng(0)
def bcal(c, sq):
    objp=board_object_points(square=sq).astype(np.float32); n=sorted(c)
    rms,K,d,_,_=cv2.calibrateCamera([objp]*len(n),[c[k].reshape(-1,1,2).astype(np.float32) for k in n],SENSOR,GUESS.copy(),None,flags=cv2.CALIB_USE_INTRINSIC_GUESS)
    return K,d
def views(z): 
    return {v:(z[f"obj/{v}"].astype(np.float32), z[f"img/{v}"].astype(np.float32)) for v in sorted(k.split('/',1)[1] for k in z.files if k.startswith('obj/'))}
def screen(vs, K, d):
    keep, drop = {}, []
    for v,(o,i) in vs.items():
        _,rv,tv=cv2.solvePnP(o.astype(np.float64),i.astype(np.float64),K,d); p,_=cv2.projectPoints(o.astype(np.float64),rv,tv,K,d)
        e=np.median(np.linalg.norm(p.reshape(-1,2)-i,axis=1))
        (keep.__setitem__(v,(o,i)) if e<=VIEW_MAX_PX else drop.append(v))
    return keep, drop
def robust_cal(vs, K0, d0, iters=ITERS):
    vs = dict(vs); npts0 = sum(len(o) for o,_ in vs.values())
    for it in range(iters+1):
        names=sorted(vs); obj=[vs[n][0] for n in names]; img=[vs[n][1] for n in names]
        rms,K,_,rv,tv=cv2.calibrateCamera(obj,img,SENSOR,K0.copy(),d0.copy(),flags=FIX)
        if it==iters: break
        res=[np.linalg.norm(cv2.projectPoints(o,r,t,K,d0)[0].reshape(-1,2)-i,axis=1) for o,i,r,t in zip(obj,img,rv,tv)]
        allr=np.concatenate(res); cut=np.median(allr)+KSIG*1.4826*np.median(np.abs(allr-np.median(allr)))
        vs={n:(o[r<=cut],i[r<=cut]) for n,o,i,r in zip(names,obj,img,res) if (r<=cut).sum()>=12}
    return K, rms, len(vs), sum(len(o) for o,_ in vs.values()), npts0
garage = cache_by_session(load_corner_cache(P4/"data/board_corners_raw.npz"), "garage_lens")
cbv = dict(np.load(SP/"cb_V.npz"))
H = views(np.load(P4/"data/lego_target_raw.npz")); V = views(np.load(SP/"lego_V.npz"))
out = {}
for dname, c in (("garage-2024", garage), ("CB-V-same-session", cbv)):
    K0,d0 = bcal(c, SQUARE_PITCH_M)
    Hk, Hd = screen(H,K0,d0); Vk, Vd = screen(V,K0,d0)
    KH,rH_rms,nH,pH,pH0 = robust_cal(Hk,K0,d0); KV,rV_rms,nV,pV,pV0 = robust_cal(Vk,K0,d0)
    rH, rV = KH[0,0]/KH[1,1], KV[0,0]/KV[1,1]
    print(f"\n[{dname} distortion]  dropped views H {Hd}  V {Vd}")
    print(f"  LEGO-H: fx/fy {rH:.5f}  rms {rH_rms:.2f}px  views {nH}  points {pH}/{pH0}   fx {KH[0,0]:.0f} fy {KH[1,1]:.0f}")
    print(f"  LEGO-V: fx/fy {rV:.5f}  rms {rV_rms:.2f}px  views {nV}  points {pV}/{pV0}   fx {KV[0,0]:.0f} fy {KV[1,1]:.0f}")
    s, t = np.sqrt(rH*rV), np.sqrt(rH/rV)
    bs=[]
    hn, vn = sorted(Hk), sorted(Vk)
    for _ in range(300):
        a={f"{k}#{j}":Hk[k] for j,k in enumerate(rng.choice(hn,len(hn)))}; b={f"{k}#{j}":Vk[k] for j,k in enumerate(rng.choice(vn,len(vn)))}
        try:
            rh=robust_cal(a,K0,d0,1)[0]; rv=robust_cal(b,K0,d0,1)[0]; rh,rv=rh[0,0]/rh[1,1], rv[0,0]/rv[1,1]
            bs.append((rh,rv,np.sqrt(rh*rv),np.sqrt(rh/rv)))
        except cv2.error: pass
    bs=np.array(bs); ci=lambda j: np.quantile(bs[:,j],[.025,.975])
    print(f"  => sensor s = {s:.5f}  CI {ci(2).round(5)}   target t = {t:.5f}  CI {ci(3).round(5)}   (bootstrap n={len(bs)})")
    print(f"     r_H CI {ci(0).round(5)}   r_V CI {ci(1).round(5)}")
    out[dname]=dict(rH=rH,rV=rV,s=s,t=t,s_ci=ci(2).tolist(),t_ci=ci(3).tolist(),dropped_H=Hd,dropped_V=Vd,nH=nH,nV=nV,rmsH=rH_rms,rmsV=rV_rms)
# checkerboard, cross-session (flagged)
for lab, sq in (("isotropic", SQUARE_SIZE_M), ("calipered", SQUARE_PITCH_M)):
    Kg,_=bcal(garage,sq); Kc,_=bcal(cbv,sq); rH,rV=Kg[0,0]/Kg[1,1],Kc[0,0]/Kc[1,1]
    print(f"\nCHECKERBOARD ({lab} pitch; H=2024 garage, V=2026 session — CROSS-SESSION): r_H {rH:.5f} r_V {rV:.5f} -> s {np.sqrt(rH*rV):.5f} t {np.sqrt(rH/rV):.5f}")
    out[f"checkerboard-{lab}"]=dict(rH=rH,rV=rV,s=float(np.sqrt(rH*rV)),t=float(np.sqrt(rH/rV)))
json.dump(out, open(SP/"roll_results.json","w"), indent=1, default=float)
