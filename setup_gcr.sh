#!/bin/bash

# Google Cloud Run 설정 스크립트
# SmartNOTAM 프로젝트용

echo "🚀 Google Cloud Run 설정 시작..."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 함수 정의
print_step() {
    echo -e "${GREEN}📋 $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 1. 인증 확인
print_step "Google Cloud 인증 상태 확인"
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    print_warning "Google Cloud 인증이 필요합니다."
    echo "다음 명령어를 실행하세요:"
    echo "gcloud auth login"
    echo "gcloud auth application-default login"
    exit 1
fi

echo "✅ 인증 완료"

# 2. 프로젝트 설정
print_step "프로젝트 설정"
echo "사용 가능한 프로젝트 목록:"
gcloud projects list --format="table(projectId,name)"

echo ""
read -p "사용할 프로젝트 ID를 입력하세요: " PROJECT_ID

if [ -z "$PROJECT_ID" ]; then
    print_error "프로젝트 ID가 입력되지 않았습니다."
    exit 1
fi

gcloud config set project $PROJECT_ID
echo "✅ 프로젝트 설정 완료: $PROJECT_ID"

# 3. API 활성화
print_step "필요한 API 활성화"
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable container.googleapis.com
echo "✅ API 활성화 완료"

# 4. Artifact Registry 설정
print_step "Artifact Registry 저장소 생성"
REGION="asia-northeast3"
REPOSITORY_NAME="smartnotam-repo"

# 저장소가 이미 존재하는지 확인
if gcloud artifacts repositories describe $REPOSITORY_NAME --location=$REGION >/dev/null 2>&1; then
    echo "✅ 저장소가 이미 존재합니다: $REPOSITORY_NAME"
else
    gcloud artifacts repositories create $REPOSITORY_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="SmartNOTAM Docker repository"
    echo "✅ Artifact Registry 저장소 생성 완료"
fi

# 5. 설정 정보 출력
print_step "설정 완료!"
echo ""
echo "📋 설정 정보:"
echo "  프로젝트 ID: $PROJECT_ID"
echo "  리전: $REGION"
echo "  저장소: $REPOSITORY_NAME"
echo ""
echo "🐳 Docker 이미지 태그:"
echo "  $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY_NAME/smartnotam"
echo ""
echo "🚀 배포 명령어:"
echo "  gcloud run deploy smartnotam \\"
echo "    --source . \\"
echo "    --platform managed \\"
echo "    --region $REGION \\"
echo "    --allow-unauthenticated \\"
echo "    --memory 2Gi \\"
echo "    --cpu 2 \\"
echo "    --timeout 900 \\"
echo "    --max-instances 10"
echo ""
echo "또는 ./deploy.sh 스크립트를 사용하세요!"

# 6. deploy.sh 파일 업데이트
print_step "deploy.sh 파일 업데이트"
sed -i.bak "s/your-project-id/$PROJECT_ID/g" deploy.sh
echo "✅ deploy.sh 파일이 업데이트되었습니다."

echo ""
echo "🎉 Google Cloud Run 설정이 완료되었습니다!"
echo "이제 './deploy.sh' 명령어로 애플리케이션을 배포할 수 있습니다."
