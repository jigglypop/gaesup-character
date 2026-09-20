# AWS 자동배포

이 배포는 S3를 영구 저장소와 불변 릴리스 저장소로 사용하고, EC2 한 대에서 API worker 하나를 실행한다. 관리 API와 화면은 기본적으로 SSM 포트 포워딩으로만 접근한다. `PublicSiteOrigin`을 설정한 경우에만 정적 화면을 80번 포트에 열며 `/api/`와 `/health`는 계속 차단한다.

## 필요한 외부 설정

- AWS CLI v2와 배포 준비용 AWS 프로필
- public access block, 기본 암호화, versioning, `BucketOwnerEnforced`가 설정된 기존 S3 버킷
- 기존 VPC와 subnet
- `OPENAI_API_KEY`, `MESHY_API_KEY`를 JSON 객체로 저장한 Secrets Manager secret
- GitHub 저장소의 `production` Environment와 환경 변수

secret 값은 다음 형태다. 저장소, 릴리스, CloudFormation parameter, GitHub 변수에는 실제 키를 넣지 않는다.

```json
{"OPENAI_API_KEY":"...","MESHY_API_KEY":"..."}
```

## 릴리스 준비

다음 명령은 버킷 보안 설정과 CloudFormation 문법을 조회하고 `dist/aws/studio.tar.gz`를 만든다. 아카이브에서 credential 경로와 위험한 상대 경로를 거부한다. `-Upload`를 주면 SHA-256 content-addressed key로 올리고 객체 metadata와 크기를 다시 확인한다. 이 단계는 EC2나 stack을 변경하지 않는다.

```powershell
./infra/prepare-aws.ps1 `
  -Profile mogaesup `
  -Region ap-northeast-2 `
  -Bucket <asset-bucket> `
  -Upload
```

결과의 `release_key`를 보관한다. 형식은 `releases/studio/<sha256>.tar.gz`다.

## 최초 EC2 stack 생성

변경 사항을 먼저 change set으로 검토한 뒤 실행한다. 다음 명령은 예시이며, 실제 리소스 ID와 ARN을 넣어야 한다.

```powershell
aws cloudformation deploy `
  --profile mogaesup `
  --region ap-northeast-2 `
  --stack-name gaesup-asset-studio `
  --template-file infra/ec2.yaml `
  --capabilities CAPABILITY_IAM `
  --parameter-overrides `
    VpcId=<vpc-id> `
    SubnetId=<subnet-id> `
    AssetBucket=<asset-bucket> `
    ReleaseKey=<release-key> `
    ProviderSecretArn=<secret-arn>
```

템플릿은 inbound port 없이 SSM 관리, IMDSv2, 암호화된 EBS, 지정 버킷의 `assets/*` 쓰기와 `releases/studio/*` 읽기만 허용한다. 부팅 시 아카이브 SHA-256을 확인한 뒤 동일한 배포 스크립트를 실행한다.

## GitHub OIDC 역할

AWS 계정에 `token.actions.githubusercontent.com` OIDC provider가 한 번은 등록되어 있어야 한다. provider audience는 `sts.amazonaws.com`이다. provider ARN을 확인한 뒤 역할 stack을 배포한다.

```powershell
aws cloudformation deploy `
  --profile mogaesup `
  --region ap-northeast-2 `
  --stack-name gaesup-asset-studio-github `
  --template-file infra/github-deploy-role.yaml `
  --capabilities CAPABILITY_IAM `
  --parameter-overrides `
    GitHubOrganization=<owner> `
    GitHubRepository=<repository> `
    GitHubEnvironment=production `
    OidcProviderArn=<github-oidc-provider-arn> `
    AssetBucket=<asset-bucket> `
    InstanceId=<instance-id>
```

신뢰 정책은 해당 저장소의 `production` Environment subject만 허용한다. GitHub 저장소의 `production` Environment에 다음 environment variable을 설정한다.

| 변수 | 값 |
| --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | 역할 stack의 `RoleArn` output |
| `AWS_REGION` | 예: `ap-northeast-2` |
| `ASSET_S3_BUCKET` | asset/release 버킷 이름 |
| `EC2_INSTANCE_ID` | 배포 대상 한 대의 instance ID |

장기 AWS access key는 GitHub에 저장하지 않는다. production Environment에 required reviewer나 branch protection을 설정하면 main 배포 승인 경계도 저장소 설정에서 관리할 수 있다.

## 자동 업데이트와 롤백

`.github/workflows/deploy-aws.yml`은 main push에서 frontend build와 Python 문법 검사를 수행한 후 불변 릴리스를 S3에 올리고 SSM Run Command로 한 인스턴스만 갱신한다. 동시 배포는 하나로 제한한다.

인스턴스 배포는 다음 순서로 진행된다.

1. S3 다운로드 checksum과 key의 SHA-256을 확인한다.
2. 기존 컨테이너를 유지한 채 새 Docker image를 build한다.
3. 기존 컨테이너를 rollback 이름으로 정지하고 candidate를 worker 하나로 실행한다.
4. `http://127.0.0.1:8080/api/health`가 `healthy` 또는 `degraded`를 반환하고 `/version.json`의 `release_sha`가 요청한 릴리스 hash와 일치하는지 최대 60초 확인한다.
5. 실패하면 candidate를 제거하고 이전 컨테이너를 원래 이름으로 복구한다. 성공하면 `/opt/asset-studio/current.json`에 영수증을 기록한다.

이전 버전으로 수동 롤백하려면 Actions의 `Run workflow`에서 이전 `release_key`를 입력한다. 새 유료 provider 작업은 제출하지 않고 저장된 애플리케이션 릴리스만 다시 배포한다. CLI에서도 같은 방식으로 실행할 수 있다.

```powershell
./infra/deploy-aws.ps1 `
  -Profile mogaesup `
  -Region ap-northeast-2 `
  -Bucket <asset-bucket> `
  -InstanceId <instance-id> `
  -ReleaseKey releases/studio/<sha256>.tar.gz
```

스크립트는 SSM command ID를 즉시 확보하고 짧은 간격으로 상태를 조회한다. 성공 영수증은 `dist/aws/deployment-receipt.json`에 남는다. `Failed`, `TimedOut`, `Cancelled`는 완료로 처리하지 않는다.

관리 화면은 다음 SSM 포트 포워딩으로 확인한다.

```powershell
aws ssm start-session `
  --profile mogaesup `
  --region ap-northeast-2 `
  --target <instance-id> `
  --document-name AWS-StartPortForwardingSession `
  --parameters portNumber=8080,localPortNumber=8080
```

세션을 연 상태에서 `http://127.0.0.1:8080/`과 `http://127.0.0.1:8080/api/health`를 확인한다. 실제 배포 완료 판정에는 Actions의 terminal success, SSM command success, 원격 health 성공이 모두 필요하다.
