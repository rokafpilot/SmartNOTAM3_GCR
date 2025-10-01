# GitHub Actions를 통한 GCR 자동 배포 설정

## 1. Google Cloud 서비스 계정 생성

### 1.1 서비스 계정 생성
```bash
# Google Cloud Console에서 또는 gcloud CLI로 실행
gcloud iam service-accounts create github-actions \
    --display-name="GitHub Actions Service Account" \
    --description="Service account for GitHub Actions deployment"
```

### 1.2 필요한 권한 부여
```bash
# 프로젝트 설정
gcloud config set project smartnotam-gcr

# 필요한 권한들
gcloud projects add-iam-policy-binding smartnotam-gcr \
    --member="serviceAccount:github-actions@smartnotam-gcr.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding smartnotam-gcr \
    --member="serviceAccount:github-actions@smartnotam-gcr.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding smartnotam-gcr \
    --member="serviceAccount:github-actions@smartnotam-gcr.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding smartnotam-gcr \
    --member="serviceAccount:github-actions@smartnotam-gcr.iam.gserviceaccount.com" \
    --role="roles/cloudbuild.builds.editor"
```

### 1.3 서비스 계정 키 생성
```bash
gcloud iam service-accounts keys create github-actions-key.json \
    --iam-account=github-actions@smartnotam-gcr.iam.gserviceaccount.com
```

## 2. GitHub 저장소 설정

### 2.1 GitHub Secrets 설정
GitHub 저장소의 Settings > Secrets and variables > Actions에서 다음 시크릿을 추가:

- **GCP_SA_KEY**: 위에서 생성한 `github-actions-key.json` 파일의 전체 내용

### 2.2 저장소 생성 및 푸시
```bash
# GitHub에서 새 저장소 생성 후
git remote add origin git@github.com:YOUR_USERNAME/SmartNOTAM3_GCR.git
git push -u origin main
```

## 3. 자동 배포 확인

### 3.1 워크플로우 실행
- 코드를 main 브랜치에 푸시하면 자동으로 GitHub Actions가 실행됩니다
- Actions 탭에서 배포 진행상황을 확인할 수 있습니다

### 3.2 배포된 서비스 확인
- 배포 완료 후 Actions 로그에서 서비스 URL을 확인할 수 있습니다
- Cloud Run 콘솔에서도 서비스 상태를 확인할 수 있습니다

## 4. 환경 변수 설정 (필요시)

Cloud Run 서비스에 환경 변수가 필요한 경우, `.github/workflows/deploy.yml` 파일의 `Deploy to Cloud Run` 단계에 다음을 추가:

```yaml
- name: Deploy to Cloud Run
  id: deploy
  uses: google-github-actions/deploy-cloudrun@v2
  with:
    service: ${{ env.SERVICE }}
    region: ${{ env.REGION }}
    image: gcr.io/${{ env.PROJECT_ID }}/${{ env.SERVICE }}:${{ github.sha }}
    flags: '--port=5000 --allow-unauthenticated --set-env-vars="ENV_VAR1=value1,ENV_VAR2=value2"'
```

## 5. 트러블슈팅

### 5.1 권한 오류
- 서비스 계정에 필요한 모든 권한이 부여되었는지 확인
- 프로젝트 ID가 올바른지 확인

### 5.2 빌드 오류
- Dockerfile이 올바른지 확인
- requirements.txt에 모든 의존성이 포함되어 있는지 확인

### 5.3 배포 오류
- Cloud Run API가 활성화되어 있는지 확인
- 리전 설정이 올바른지 확인
