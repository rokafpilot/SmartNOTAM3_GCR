#!/bin/bash

# SmartNOTAM 새로운 Cloud Run 배포 스크립트

# 설정 - 여기에 새로운 프로젝트 정보를 입력하세요
PROJECT_ID="smartnotam3-474002"  # 기존 프로젝트 ID
REGION="asia-northeast3"
SERVICE_NAME="smartnotam"
REPOSITORY_NAME="smartnotam-repo"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_step() {
    echo -e "${GREEN}📋 $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

echo "🚀 SmartNOTAM 새로운 Cloud Run 배포 시작..."

# 1. 프로젝트 설정 확인
print_step "프로젝트 설정 확인"
if [ "$PROJECT_ID" = "your-new-project-id" ]; then
    print_error "PROJECT_ID를 실제 프로젝트 ID로 변경해주세요!"
    echo "스크립트 상단의 PROJECT_ID 변수를 수정하세요."
    exit 1
fi

gcloud config set project $PROJECT_ID
echo "✅ 프로젝트 설정: $PROJECT_ID"

# 2. 필요한 API 활성화
print_step "API 활성화 중..."
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
echo "✅ API 활성화 완료"

# 3. Artifact Registry 저장소 생성 (이미 존재하면 무시)
print_step "Artifact Registry 저장소 생성 중..."
gcloud artifacts repositories create $REPOSITORY_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="SmartNOTAM Docker repository" \
    2>/dev/null || echo "✅ 저장소가 이미 존재합니다."

# 4. Docker 이미지 빌드 및 푸시
print_step "Docker 이미지 빌드 및 푸시 중..."
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY_NAME/$SERVICE_NAME

# 5. Cloud Run 서비스 배포
print_step "Cloud Run 서비스 배포 중..."
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
    --set-env-vars="FLASK_ENV=production,GOOGLE_API_KEY=AIzaSyA7xSPOdZXy3DeQ-zphOcZQlchB-Q9k10k,GOOGLE_MAPS_API_KEY=AIzaSyA7xSPOdZXy3DeQ-zphOcZQlchB-Q9k10k"

# 6. 서비스 URL 출력
echo "✅ 배포 완료!"
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo "🌐 서비스 URL: $SERVICE_URL"

# 7. 헬스 체크
print_step "헬스 체크 중..."
sleep 10
curl -f "$SERVICE_URL/health" && echo "✅ 헬스 체크 성공!" || echo "❌ 헬스 체크 실패"

echo ""
echo "🎉 새로운 Cloud Run 배포가 완료되었습니다!"
echo "🌐 접속 URL: $SERVICE_URL"
echo ""
echo "📝 추가 설정이 필요한 경우:"
echo "  - 도메인 연결: gcloud run domain-mappings create"
echo "  - SSL 인증서: 자동으로 관리됨"
echo "  - 로그 확인: gcloud run logs tail $SERVICE_NAME --region $REGION"
