#!/bin/bash

# SmartNOTAM Cloud Run 배포 스크립트

# 설정
PROJECT_ID="smartnotam3"
REGION="asia-northeast3"
SERVICE_NAME="smartnotam"
REPOSITORY_NAME="smartnotam-repo"

echo "🚀 SmartNOTAM Cloud Run 배포 시작..."

# 1. 프로젝트 설정
echo "📋 프로젝트 설정 중..."
gcloud config set project $PROJECT_ID

# 2. 필요한 API 활성화
echo "🔧 API 활성화 중..."
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# 3. Artifact Registry 저장소 생성 (이미 존재하면 무시)
echo "📦 Artifact Registry 저장소 생성 중..."
gcloud artifacts repositories create $REPOSITORY_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="SmartNOTAM Docker repository" \
    2>/dev/null || echo "저장소가 이미 존재합니다."

# 4. Docker 이미지 빌드 및 푸시
echo "🐳 Docker 이미지 빌드 중..."
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY_NAME/$SERVICE_NAME

# 5. Cloud Run 서비스 배포
echo "☁️ Cloud Run 서비스 배포 중..."
gcloud run deploy $SERVICE_NAME \
    --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY_NAME/$SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 900 \
    --max-instances 10 \
    --port 8080 \
    --set-env-vars="FLASK_ENV=production"

# 6. 서비스 URL 출력
echo "✅ 배포 완료!"
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo "🌐 서비스 URL: $SERVICE_URL"

# 7. 헬스 체크
echo "🔍 헬스 체크 중..."
sleep 10
curl -f "$SERVICE_URL/health" && echo "✅ 헬스 체크 성공!" || echo "❌ 헬스 체크 실패"

echo "🎉 배포가 완료되었습니다!"
