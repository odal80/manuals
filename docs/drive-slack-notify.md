# 구글 드라이브 → 슬랙 업데이트 알림

## 목적
지정한 구글 드라이브 폴더에 **새 파일이 추가되거나 기존 파일이 변경되면** 슬랙 채널로 자동 공지합니다.

## 동작 방식
1. GitHub Actions 워크플로(`.github/workflows/drive-slack-notify.yml`)가 **매시간(cron)** 실행됩니다.
2. 서비스 계정으로 대상 드라이브 폴더(및 하위 폴더 전체)를 확인합니다.
3. 직전 상태가 저장된 매니페스트 파일(`state/drive-manifest.json`)과 비교합니다.
4. 새 파일 / 변경된 파일을 찾아 **슬랙 incoming webhook** 으로 전송합니다.
5. 처리 후 최신 상태를 매니페스트에 다시 저장(커밋)합니다.

> **첫 실행**은 알림을 보내지 않고 **기준선(baseline)만 저장**합니다. 이후 실행부터 변경분을 비교·공지하므로 처음에 대량 알림이 오지 않습니다.

## 설정 순서 (사용자가 직접 해야 함)
1. **서비스 계정 생성 및 Drive API 설정**
   - Google Cloud Console에서 프로젝트를 선택하거나 새로 만듭니다.
   - **서비스 계정(Service Account)** 을 생성하고 **JSON 키**를 발급·다운로드합니다.
   - 해당 프로젝트에서 **Google Drive API** 를 사용 설정합니다.
2. **드라이브 폴더 공유**
   - 모니터링할 드라이브 폴더를 서비스 계정 이메일(`...@....iam.gserviceaccount.com`)에 **뷰어(Viewer)로 공유**합니다.
   - 대상이 **공유 드라이브(Shared Drive)** 인 경우에는 서비스 계정을 해당 공유 드라이브의 **멤버로 추가**합니다.
3. **GitHub Secrets 등록**
   - 저장소 **Settings → Secrets and variables → Actions** 로 이동합니다.
   - secret 2개를 등록합니다.
     - `GDRIVE_SA_JSON` : 서비스 계정 **JSON 키 파일 전체 내용**
     - `SLACK_WEBHOOK_URL` : **슬랙 incoming webhook URL**
4. **슬랙 incoming webhook 생성**
   - 공지를 받을 채널에 대해 슬랙 **incoming webhook** 을 생성하고, 그 URL을 위 `SLACK_WEBHOOK_URL` 에 넣습니다.

## 수동 테스트
- GitHub 저장소의 **Actions** 탭에서 `Drive to Slack notifier` 워크플로를 선택하고 **`Run workflow`** 버튼으로 즉시 실행할 수 있습니다.

## 실행 주기 변경
- 워크플로 파일의 `cron` 값을 수정합니다.
- cron 시간은 **UTC 기준**입니다. (예: `0 * * * *` = 매시 정각 UTC) 실제 실행은 GitHub 사정으로 다소 지연될 수 있습니다.

## 대상 폴더 변경
- 모니터링 폴더를 바꾸려면 다음 중 하나를 수정합니다.
  - 워크플로의 환경변수(`env`)에 `DRIVE_FOLDER_ID` 를 추가/수정
  - 또는 스크립트 `scripts/drive_slack_notify.py` 의 `DRIVE_FOLDER_ID` 기본값 수정

## 안전 장치
- `GDRIVE_SA_JSON` 또는 `SLACK_WEBHOOK_URL` secret이 **설정되어 있지 않으면** 워크플로는 아무 작업도 하지 않고 **정상 종료**합니다. 따라서 설정을 완료하기 전까지는 안전하게 비활성 상태로 유지됩니다.

## 모니터링 범위
- 지정한 폴더와 **그 하위 폴더에 포함된 모든 파일**(하위 폴더 재귀 탐색 포함)을 대상으로 합니다. (폴더 자체는 알림 대상이 아니며 파일만 감지)
