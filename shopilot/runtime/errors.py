class ProviderError(RuntimeError):
    def __init__(self,code:str,message:str,retryable:bool=False):
        super().__init__(message); self.code=code; self.retryable=retryable

def classify_provider_error(exc:Exception)->ProviderError:
    name=type(exc).__name__.lower(); text=str(exc).lower()
    if "auth" in name or "401" in text: return ProviderError("provider_authentication_failed","模型服务认证失败",False)
    if "rate" in name or "429" in text: return ProviderError("provider_rate_limited","模型服务限流",True)
    if "timeout" in name or "timeout" in text: return ProviderError("provider_timeout","模型服务超时",True)
    if "validation" in name or "schema" in text: return ProviderError("provider_structured_output_invalid","模型结构化输出无效",True)
    return ProviderError("provider_error","模型服务调用失败",False)
