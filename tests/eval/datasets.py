"""LangSmith 데이터셋 생성 및 관리.

실제 agent 실행에서 발생한 trace를 Dataset으로 추가하거나,
seed 예제를 직접 등록하는 유틸리티를 제공한다.
"""

from langsmith import Client

DATASET_NAME = "okdoit-think-node"

# think 노드 평가용 seed 예제들.
# 실제 trace가 쌓이면 LangSmith UI에서 trace → dataset 추가로 보강한다.
SEED_EXAMPLES: list[dict] = [
    {
        "inputs": {
            "task": "네이버에서 날씨를 검색해줘",
            "dom_text": (
                "[Page Info]\n"
                "Title: NAVER\n"
                "URL: https://www.naver.com\n\n"
                "[Clickable Elements]\n"
                "1. [input] type=text placeholder=검색어를 입력해 주세요.\n"
                "2. [button] 검색\n"
            ),
            "current_url": "https://www.naver.com",
            "subtasks": [{"description": "네이버 검색창에 날씨 검색", "done": False}],
            "messages": [],
            "last_action_error": None,
        },
        "outputs": {
            "expected_action_type": "type",
        },
    },
    {
        "inputs": {
            "task": "구글에서 파이썬 튜토리얼을 찾아줘",
            "dom_text": (
                "[Page Info]\n"
                "Title: Google\n"
                "URL: https://www.google.com\n\n"
                "[Clickable Elements]\n"
                "1. [input] type=text placeholder=Google 검색\n"
                "2. [button] Google 검색\n"
            ),
            "current_url": "https://www.google.com",
            "subtasks": [{"description": "구글 검색창에 파이썬 튜토리얼 입력", "done": False}],
            "messages": [],
            "last_action_error": None,
        },
        "outputs": {
            "expected_action_type": "type",
        },
    },
    {
        "inputs": {
            "task": "위키피디아에서 인공지능 문서를 열어줘",
            "dom_text": (
                "[Page Info]\n"
                "Title: Google\n"
                "URL: https://www.google.com\n\n"
                "[Clickable Elements]\n"
                "1. [input] type=text placeholder=Google 검색\n"
            ),
            "current_url": "https://www.google.com",
            "subtasks": [{"description": "위키피디아 인공지능 페이지 이동", "done": False}],
            "messages": [],
            "last_action_error": None,
        },
        "outputs": {
            "expected_action_type": "navigate",
        },
    },
]


def get_or_create_dataset(client: Client, dataset_name: str = DATASET_NAME):
    """데이터셋이 없으면 생성하고, 있으면 기존 것을 반환한다.

    Args:
        client: LangSmith Client 인스턴스
        dataset_name: 데이터셋 이름

    Returns:
        Dataset 객체
    """
    datasets = list(client.list_datasets(dataset_name=dataset_name))
    if datasets:
        return datasets[0]
    return client.create_dataset(dataset_name, description="think 노드 액션 결정 평가용 데이터셋")


def seed_dataset(client: Client, dataset_name: str = DATASET_NAME) -> None:
    """seed 예제가 없는 경우에만 SEED_EXAMPLES를 데이터셋에 추가한다.

    중복 추가를 방지하기 위해 기존 예제 수를 확인한다.

    Args:
        client: LangSmith Client 인스턴스
        dataset_name: 대상 데이터셋 이름
    """
    dataset = get_or_create_dataset(client, dataset_name)
    existing = list(client.list_examples(dataset_id=dataset.id))

    if existing:
        print(f"[dataset] '{dataset_name}' 이미 {len(existing)}개 예제 존재. seed 스킵.")
        return

    client.create_examples(
        dataset_id=dataset.id,
        inputs=[ex["inputs"] for ex in SEED_EXAMPLES],
        outputs=[ex["outputs"] for ex in SEED_EXAMPLES],
    )
    print(f"[dataset] '{dataset_name}'에 seed {len(SEED_EXAMPLES)}개 추가 완료.")


def add_example_from_trace(
    client: Client,
    run_id: str,
    expected_action_type: str,
    dataset_name: str = DATASET_NAME,
) -> None:
    """실제 trace run을 데이터셋 예제로 추가한다.

    LangSmith에 저장된 run의 inputs를 그대로 가져와 새 예제를 만든다.
    실패한 run이나 흥미로운 edge case를 발견했을 때 사용한다.

    Args:
        client: LangSmith Client 인스턴스
        run_id: 데이터셋에 추가할 LangSmith run ID
        expected_action_type: 이 상황에서 기대하는 올바른 action type
        dataset_name: 대상 데이터셋 이름
    """
    dataset = get_or_create_dataset(client, dataset_name)
    run = client.read_run(run_id)

    client.create_example(
        dataset_id=dataset.id,
        inputs=run.inputs,
        outputs={"expected_action_type": expected_action_type},
    )
    print(f"[dataset] run {run_id[:8]}... 을 '{dataset_name}'에 추가 완료.")
