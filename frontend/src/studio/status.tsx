import { useEffect, useRef } from 'react';
import type { AvatarRuntime } from '../avatar/runtime/AvatarRuntime';
import { StudioIcon } from './icons';

type Props = { open: boolean; onClose(): void; diagnostics?: ReturnType<AvatarRuntime['getDiagnostics']>; assets: number; backend: string; connected: boolean };

export function ImplementationStatus({ open, onClose, diagnostics, assets, backend, connected }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (open) dialog.current?.showModal(); else dialog.current?.close(); }, [open]);
  const features = [
    ['공통 스켈레톤', diagnostics ? `${diagnostics.boneCount}개 bone · 하나의 rig` : '모델 초기화 중', !!diagnostics],
    ['파츠 장착·해제', diagnostics ? `${diagnostics.parts}개 파츠 조립됨` : '초기화 대기', !!diagnostics],
    ['동작 공유', diagnostics ? `${diagnostics.animation || 'idle'} · mixer 유지` : '초기화 대기', !!diagnostics],
    ['몸 마스킹', '장착된 파츠의 몸 영역 합집합', !!diagnostics],
    ['에셋 카탈로그', `${assets}종 · 수동 에셋과 사용자 생산 버전`, assets > 0],
    ['장착 저장·복구', '서버 API · revision 충돌 검사 · 응답 유실 복구', connected],
    ['LOD · 소켓', `수동 LOD 0/1 · 머리 / 등 / 손`, !!diagnostics],
  ] as const;
  return <dialog ref={dialog} className="implementation-dialog" onClose={onClose}>
    <div className="dialog-heading"><div><span className="panel-kicker">BUILD OVERVIEW</span><h2>구현 현황</h2></div><button className="icon-button" aria-label="구현 현황 닫기" onClick={onClose}><StudioIcon name="close" /></button></div>
    <p className="dialog-intro">현재 프론트에서 실행하는 기능과 다음 연결 단계를 확인합니다.</p>
    <div className="runtime-banner"><span className="live-dot" /><strong>{backend === 'webgpu' ? 'WebGPU 실행 중' : backend === 'webgl-fallback' ? 'WebGL 호환 모드 실행 중' : '렌더러 초기화 중'}</strong><span>R3F · gaesup-world</span></div>
    <div className="feature-list">{features.map(([title, description, ready]) => <div className="feature-row" key={title}><span className={`feature-indicator ${ready ? 'ready' : ''}`}><StudioIcon name={ready ? 'check' : 'activity'} size={15} /></span><div><strong>{title}</strong><p>{description}</p></div><small>{ready ? '사용 가능' : '대기'}</small></div>)}</div>
    <p className="dialog-intro"><a href="/avatar.html">이미지 파츠 → 개별 Meshy → Blender 공통 리그 생산 화면 열기</a></p>
    <div className="next-connections"><span className="panel-kicker">NEXT CONNECTIONS</span><h3>연결되지 않은 기능</h3><div><span>Tripo 생성 자동화</span><span>네트워크 동기화</span><span>Spring bone · KTX2</span></div><p>이미지·3D 생산 작업과 외형 승인 상태는 생산 버전별로 확인합니다. 기술 검증과 외형 승인은 별개입니다.</p></div>
  </dialog>;
}
