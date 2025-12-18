# Dyanbox - Dynamic Malware Analysis Sandbox

QEMU/KVM을 활용한 Windows PE 파일 자동 동적 분석 플랫폼입니다.

## 주요 기능

- **자동화된 분석**: 안전한 샌드박스 환경에서 Windows PE 파일을 자동으로 실행하고 분석합니다.
- **QEMU/KVM 통합**: 하드웨어 가속 가상화를 사용하여 분석 대상을 격리합니다.
- **에이전트 기반 모니터링**: 게스트 OS 내부의 행위(프로세스, 네트워크, 파일 시스템)를 캡처합니다.

## 프로젝트 구조

- `src/api`: 파일 제출 및 제어를 위한 REST API 서버입니다.
- `src/engine`: VM 관리(libvirt) 및 분석 오케스트레이션 핵심 로직입니다.
- `src/agent`: 게스트 OS(Windows) 내부에서 실행되는 Python 에이전트입니다.
- `config`: 프로젝트 설정 파일입니다.

## 사전 요구 사항

- Linux 호스트 (KVM 지원 필수)
- Python 3.10 이상
- QEMU/KVM 및 libvirt
- Windows VM 이미지 (qcow2)

## 설치 및 실행

1. 의존성 패키지 설치:
   ```bash
   pip install -r requirements.txt
   ```

2. `config/settings.py`에서 VM 경로 및 설정 확인.

3. API 서버 실행:
   ```bash
   uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
   ```
