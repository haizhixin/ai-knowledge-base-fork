#!/usr/bin/env python3
"""统一 LLM 调用客户端模块。

支持 DeepSeek、Qwen、OpenAI 三种模型提供商，通过环境变量切换。
使用 httpx 直接调用 OpenAI 兼容 API，不依赖 openai SDK。

用法：
    from pipeline.model_client import quick_chat, LLMClient

    # 快速调用
    response = quick_chat("你好，介绍一下自己")

    # 完整客户端
    client = LLMClient.from_env()
    response = client.chat([{"role": "user", "content": "Hello"}])

环境变量：
    LLM_PROVIDER: 模型提供商，可选 deepseek/qwen/openai，默认 deepseek
    DEEPSEEK_API_KEY: DeepSeek API Key
    QWEN_API_KEY: 通义千问 API Key
    OPENAI_API_KEY: OpenAI API Key
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

# 自动加载 .env 文件
try:
    from dotenv import load_dotenv
    # 从项目根目录加载 .env
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv 未安装时忽略

logger = logging.getLogger(__name__)


class LLMProviderType(Enum):
    """支持的 LLM 提供商类型。"""

    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    OPENAI = "openai"


@dataclass
class Usage:
    """Token 用量统计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        """支持用量累加。"""
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class LLMResponse:
    """LLM 响应结果。"""

    content: str
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    provider: str = ""
    latency_ms: float = 0.0
    finish_reason: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)


# 各提供商配置
PROVIDER_CONFIG: dict[LLMProviderType, dict[str, Any]] = {
    LLMProviderType.DEEPSEEK: {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
        # 价格: USD per 1M tokens (prompt, completion)
        "pricing": (0.14, 0.28),
    },
    LLMProviderType.QWEN: {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "env_key": "QWEN_API_KEY",
        "pricing": (0.40, 1.20),
    },
    LLMProviderType.OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
        "pricing": (0.15, 0.60),
    },
}


class LLMProvider(ABC):
    """LLM 提供商抽象基类。

    定义统一接口，所有具体提供商需实现此接口。
    """

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """发送聊天请求。

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]。
            model: 模型名称，为 None 时使用默认模型。
            temperature: 温度参数，控制随机性。
            max_tokens: 最大输出 token 数。
            **kwargs: 其他参数。

        Returns:
            LLM 响应结果。

        Raises:
            LLMError: LLM 调用失败。
        """
        pass

    @abstractmethod
    def get_api_key(self) -> str:
        """获取 API Key。

        Returns:
            API Key 字符串。
        """
        pass


class LLMError(Exception):
    """LLM 调用错误。"""

    def __init__(self, message: str, provider: str = "", status_code: int = 0) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容 API 提供商实现。

    通过 httpx 调用 OpenAI 兼容的 API 接口。
    """

    def __init__(
        self,
        provider_type: LLMProviderType,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        """初始化提供商。

        Args:
            provider_type: 提供商类型。
            api_key: API Key，为 None 时从环境变量读取。
            base_url: API 基础 URL，为 None 时使用默认值。
            default_model: 默认模型名称。
            timeout: 请求超时时间（秒）。
        """
        self.provider_type = provider_type
        self.config = PROVIDER_CONFIG[provider_type]

        self._api_key = api_key or os.getenv(self.config["env_key"], "")
        if not self._api_key:
            raise LLMError(
                f"缺少 API Key: 请设置环境变量 {self.config['env_key']}",
                provider=provider_type.value,
            )

        self._base_url = (base_url or self.config["base_url"]).rstrip("/")
        self._default_model = default_model or self.config["default_model"]
        self._timeout = timeout

        logger.info(
            "初始化 LLM 客户端: provider=%s, base_url=%s, model=%s",
            provider_type.value,
            self._base_url,
            self._default_model,
        )

    def get_api_key(self) -> str:
        """获取 API Key。"""
        return self._api_key

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """发送聊天请求。

        Args:
            messages: 消息列表。
            model: 模型名称。
            temperature: 温度参数。
            max_tokens: 最大输出 token 数。
            **kwargs: 其他参数（如 top_p, stop 等）。

        Returns:
            LLM 响应结果。

        Raises:
            LLMError: 调用失败。
        """
        model = model or self._default_model
        url = f"{self._base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        payload.update(kwargs)

        logger.debug("发送请求: url=%s, model=%s", url, model)
        start_time = time.perf_counter()

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code != 200:
                    error_body = response.text[:500]
                    raise LLMError(
                        f"API 请求失败: status={response.status_code}, body={error_body}",
                        provider=self.provider_type.value,
                        status_code=response.status_code,
                    )

                data = response.json()

        except httpx.TimeoutException as e:
            raise LLMError(
                f"请求超时: {self._timeout}s",
                provider=self.provider_type.value,
            ) from e
        except httpx.RequestError as e:
            raise LLMError(
                f"网络请求错误: {e}",
                provider=self.provider_type.value,
            ) from e

        # 解析响应
        try:
            choices = data.get("choices", [])
            if not choices:
                raise LLMError("响应无 choices", provider=self.provider_type.value)

            content = choices[0].get("message", {}).get("content", "")
            finish_reason = choices[0].get("finish_reason", "")

            usage_data = data.get("usage", {})
            usage = Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(
                f"响应解析失败: {e}",
                provider=self.provider_type.value,
            ) from e

        logger.info(
            "LLM 响应: model=%s, tokens=%d, latency=%.1fms",
            model,
            usage.total_tokens,
            latency_ms,
        )

        return LLMResponse(
            content=content,
            usage=usage,
            model=model,
            provider=self.provider_type.value,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            raw_response=data,
        )


class LLMClient:
    """统一 LLM 客户端。

    封装提供商选择和调用逻辑。
    """

    def __init__(self, provider: LLMProvider) -> None:
        """初始化客户端。

        Args:
            provider: LLM 提供商实例。
        """
        self._provider = provider
        self._total_usage = Usage()

    @classmethod
    def from_env(cls, provider_name: str | None = None) -> LLMClient:
        """从环境变量创建客户端。

        Args:
            provider_name: 提供商名称，为 None 时从 LLM_PROVIDER 环境变量读取。

        Returns:
            LLMClient 实例。

        Raises:
            LLMError: 不支持的提供商或缺少 API Key。
        """
        provider_name = provider_name or os.getenv("LLM_PROVIDER", "deepseek").lower()

        provider_map = {
            "deepseek": LLMProviderType.DEEPSEEK,
            "qwen": LLMProviderType.QWEN,
            "openai": LLMProviderType.OPENAI,
        }

        if provider_name not in provider_map:
            raise LLMError(
                f"不支持的提供商: {provider_name}，可选: {list(provider_map.keys())}"
            )

        provider_type = provider_map[provider_name]
        provider = OpenAICompatibleProvider(provider_type)

        return cls(provider)

    @property
    def total_usage(self) -> Usage:
        """获取累计用量。"""
        return self._total_usage

    @property
    def provider(self) -> LLMProvider:
        """获取提供商实例。"""
        return self._provider

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """发送聊天请求。

        Args:
            messages: 消息列表。
            model: 模型名称。
            temperature: 温度参数。
            max_tokens: 最大输出 token 数。
            **kwargs: 其他参数。

        Returns:
            LLM 响应结果。
        """
        response = self._provider.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        self._total_usage += response.usage
        return response

    def estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数量。

        使用简单的启发式方法：英文约 4 字符 = 1 token，中文约 1.5 字符 = 1 token。

        Args:
            text: 待估算的文本。

        Returns:
            估算的 token 数量。
        """
        if not text:
            return 0

        # 统计中英文字符
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars

        # 中文约 1.5 字符/token，英文约 4 字符/token
        estimated = int(chinese_chars / 1.5 + other_chars / 4)

        return max(1, estimated)

    def calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        provider_type: LLMProviderType | None = None,
    ) -> float:
        """计算调用成本（USD）。

        Args:
            prompt_tokens: 输入 token 数。
            completion_tokens: 输出 token 数。
            provider_type: 提供商类型，为 None 时使用当前提供商。

        Returns:
            成本（美元）。
        """
        if provider_type is None:
            provider_type = self._provider.provider_type

        pricing = PROVIDER_CONFIG[provider_type]["pricing"]
        prompt_price, completion_price = pricing

        # 价格是每 1M tokens
        cost = (
            prompt_tokens * prompt_price / 1_000_000
            + completion_tokens * completion_price / 1_000_000
        )

        return cost

    def get_usage_report(self) -> dict[str, Any]:
        """获取用量报告。

        Returns:
            包含用量统计和成本的报告。
        """
        provider_type = self._provider.provider_type
        pricing = PROVIDER_CONFIG[provider_type]["pricing"]

        cost = self.calculate_cost(
            self._total_usage.prompt_tokens,
            self._total_usage.completion_tokens,
        )

        return {
            "provider": provider_type.value,
            "prompt_tokens": self._total_usage.prompt_tokens,
            "completion_tokens": self._total_usage.completion_tokens,
            "total_tokens": self._total_usage.total_tokens,
            "cost_usd": round(cost, 6),
            "pricing_per_million": {
                "prompt": pricing[0],
                "completion": pricing[1],
            },
        }


def chat_with_retry(
    client: LLMClient,
    messages: list[dict[str, str]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs: Any,
) -> LLMResponse:
    """带重试的聊天请求。

    Args:
        client: LLM 客户端。
        messages: 消息列表。
        max_retries: 最大重试次数。
        base_delay: 基础延迟（秒），指数退避。
        **kwargs: 传递给 chat() 的其他参数。

    Returns:
        LLM 响应结果。

    Raises:
        LLMError: 所有重试均失败。
    """
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return client.chat(messages, **kwargs)

        except LLMError as e:
            last_error = e

            # 4xx 错误不重试
            if 400 <= e.status_code < 500 and e.status_code != 429:
                raise

            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "LLM 调用失败，%0.1f 秒后重试 (第 %d/%d 次): %s",
                    delay,
                    attempt + 1,
                    max_retries,
                    str(e)[:100],
                )
                time.sleep(delay)

    raise last_error or LLMError("未知错误")


def quick_chat(
    prompt: str,
    system_prompt: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """快速聊天便捷函数。

    一句话调用 LLM，只返回文本内容。

    Args:
        prompt: 用户提示词。
        system_prompt: 系统提示词，可选。
        provider: 提供商名称，为 None 时从环境变量读取。
        model: 模型名称。
        temperature: 温度参数。
        max_tokens: 最大输出 token 数。

    Returns:
        LLM 响应文本内容。

    Example:
        >>> response = quick_chat("用一句话介绍 Python")
        >>> print(response)
    """
    client = LLMClient.from_env(provider)

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = chat_with_retry(
        client,
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.content


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    # 测试代码
    print("=" * 60)
    print("LLM 客户端测试")
    print("=" * 60)

    # 检查环境变量
    provider_name = os.getenv("LLM_PROVIDER", "deepseek")
    print(f"\n当前提供商: {provider_name}")

    try:
        # 创建客户端
        client = LLMClient.from_env()
        print(f"客户端初始化成功")

        # 测试 token 估算
        test_text = "你好，这是一段测试文本，包含中文和 English。"
        estimated = client.estimate_tokens(test_text)
        print(f"\nToken 估算测试:")
        print(f"  文本: {test_text}")
        print(f"  估算 tokens: {estimated}")

        # 测试成本计算
        print(f"\n成本计算测试:")
        cost = client.calculate_cost(1000, 500)
        print(f"  1000 prompt + 500 completion tokens = ${cost:.6f}")

        # 测试聊天（如果有 API Key）
        print(f"\n聊天测试:")
        print(f"  发送: 你好，请用一句话介绍自己")

        response = chat_with_retry(
            client,
            [{"role": "user", "content": "你好，请用一句话介绍自己"}],
            max_tokens=100,
        )

        print(f"  响应: {response.content}")
        print(f"  用量: {response.usage.total_tokens} tokens")
        print(f"  延迟: {response.latency_ms:.1f}ms")

        # 用量报告
        report = client.get_usage_report()
        print(f"\n用量报告:")
        print(f"  总 tokens: {report['total_tokens']}")
        print(f"  成本: ${report['cost_usd']:.6f}")

        # 测试 quick_chat
        print(f"\nquick_chat 测试:")
        result = quick_chat(
            "1+1等于几？只回答数字。",
            max_tokens=10,
        )
        print(f"  结果: {result}")

    except LLMError as e:
        print(f"错误: {e}")
        print(f"请设置相应的 API Key 环境变量")

    except Exception as e:
        print(f"未知错误: {e}")
        raise
