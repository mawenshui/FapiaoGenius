"""AI 服务 — DeepSeek API 集成

基于 DeepSeek 官方 API (https://api-docs.deepseek.com/zh-cn/)
- Base URL: https://api.deepseek.com
- Models: deepseek-v4-flash / deepseek-v4-pro
- 兼容 OpenAI Chat Completions 格式

重构后：
- AI 接收 pdfplumber 原始文本，返回各字段的正则表达式
- 本地用返回的正则对原始文本做提取，获得发票字段值
- 规则学习同样返回 extraction_config（正则字典）
"""

import json
import re
import ssl
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
from database.config_dao import config_dao
from models.ai_config import AIConfig
from core.logger import logger
from core.exceptions import AIServiceError
from utils.crypto import encrypt_key, decrypt_key
from utils.validators import normalize_date, parse_amount


class AIService:
    """AI 服务"""

    # DeepSeek API 默认配置
    DEFAULT_API_URL = "https://api.deepseek.com"
    DEFAULT_MODEL = "deepseek-v4-flash"

    _TIMEOUT = 90

    def __init__(self):
        self._config: Optional[AIConfig] = None

    def get_config(self) -> AIConfig:
        if self._config is None:
            self._config = config_dao.get()
            if not self._config.api_url:
                self._config.api_url = self.DEFAULT_API_URL
            if not self._config.model_name:
                self._config.model_name = self.DEFAULT_MODEL
            if self._config.api_key:
                self._config.api_key = decrypt_key(self._config.api_key)
        return self._config

    def save_config(self, config: AIConfig):
        if config.api_key:
            config.api_key = encrypt_key(config.api_key)
        config_dao.save(config)
        self._config = None

    # ── 统一 API 调用 ───────────────────────────────────────────

    def _call_api(self, messages: list, temperature: float = 0.1,
                  use_json_format: bool = True,
                  return_raw: bool = False) -> dict:
        config = self.get_config()

        if not config.api_url:
            raise AIServiceError("API 地址未配置")
        if not config.api_key:
            raise AIServiceError("API Key 未配置")
        if not config.model_name:
            raise AIServiceError("模型名称未配置")

        base_url = config.api_url.rstrip('/')
        url = f"{base_url}/chat/completions"

        payload = {
            "model": config.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if use_json_format:
            payload["response_format"] = {"type": "json_object"}

        if config.model_name.startswith('deepseek-v4'):
            payload["thinking"] = {"type": "disabled"}

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        logger.debug(
            f"[AI调用] 模型={config.model_name}, URL={url}, "
            f"消息数={len(messages)}, JSON格式={use_json_format}"
        )

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}",
            },
            method="POST",
        )

        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, timeout=self._TIMEOUT, context=ctx) as resp:
                body = resp.read().decode("utf-8")
                resp_data = json.loads(body)

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            logger.error(f"[AI调用] HTTP错误: {e.code}, 响应: {error_body[:500]}")
            self._handle_http_error(e.code, error_body)

        except urllib.error.URLError as e:
            raise AIServiceError(f"无法连接到 AI 服务 ({base_url}): {e.reason}")

        except json.JSONDecodeError as e:
            raise AIServiceError(f"AI 返回数据格式异常: {e}")

        except Exception as e:
            if "timed out" in str(e).lower():
                raise AIServiceError(f"请求超时（{self._TIMEOUT}秒），请检查网络连接")
            raise AIServiceError(f"API 调用失败: {e}")

        try:
            choices = resp_data.get("choices", [])
            if not choices:
                raise AIServiceError("AI 返回为空（无 choices）")

            content = choices[0]["message"]["content"]

            # 记录 AI 响应原始内容（DEBUG），便于排查正则截断等问题
            usage = resp_data.get("usage", {})
            logger.debug(
                f"[AI响应] 模型={config.model_name}, "
                f"token用量={usage.get('total_tokens', '?')} "
                f"(prompt={usage.get('prompt_tokens', '?')}, "
                f"completion={usage.get('completion_tokens', '?')})"
            )
            logger.debug(f"[AI响应] 原始内容 ({len(content)} 字符):\n{content}")

            if return_raw:
                return {"text": content}

            result = json.loads(content)
            return result

        except (KeyError, IndexError) as e:
            raise AIServiceError(f"AI 响应结构异常: {e}")
        except json.JSONDecodeError:
            logger.debug(f"[AI响应] JSON解析失败，尝试从文本中提取: {content[:200]}...")
            result = self._extract_json_from_text(content)
            if result:
                logger.debug(f"[AI响应] 从文本中提取JSON成功")
                return result
            raise AIServiceError("AI 返回内容无法解析为 JSON")

    def _handle_http_error(self, code: int, error_body: str):
        error_msg = ""
        try:
            err_data = json.loads(error_body)
            error_msg = err_data.get("error", {}).get("message", error_body)
        except Exception:
            error_msg = error_body or f"HTTP {code}"

        if code in (401, 403):
            raise AIServiceError(f"API Key 无效或已过期（HTTP {code}）")
        elif code == 429:
            raise AIServiceError("请求频率超限，请稍后重试")
        elif code == 400 and "response_format" in error_msg.lower():
            raise AIServiceError("__retry_no_json_format__")
        elif 500 <= code < 600:
            raise AIServiceError(f"AI 服务端错误（HTTP {code}），请稍后重试")
        else:
            raise AIServiceError(f"API 请求失败（HTTP {code}）: {error_msg[:200]}")

    @staticmethod
    def _extract_json_from_text(text: str) -> Optional[dict]:
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    # ── 文本提取 ────────────────────────────────────────────────

    @staticmethod
    def _extract_text_for_ai(file_path: str) -> str:
        """从发票文件中提取纯文本，供 AI 分析"""
        ext = Path(file_path).suffix.lower()

        if ext == '.pdf':
            try:
                from parsers.text_extractor import TextExtractor
                return TextExtractor.extract_text(file_path)
            except Exception as e:
                logger.warning(f"PDF 文本提取失败: {e}")
                return ""

        elif ext == '.xml':
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(file_path)
                root = tree.getroot()
                texts = []
                for elem in root.iter():
                    if elem.text:
                        t = elem.text.strip()
                        if t:
                            texts.append(t)
                    if elem.tail:
                        t = elem.tail.strip()
                        if t:
                            texts.append(t)
                return '\n'.join(texts)
            except Exception as e:
                logger.warning(f"XML 文本提取失败: {e}")
                return ""

        elif ext == '.ofd':
            try:
                import zipfile
                import xml.etree.ElementTree as ET
                texts = []
                with zipfile.ZipFile(file_path, 'r') as zf:
                    for name in zf.namelist():
                        if name.endswith('.xml'):
                            content = zf.read(name)
                            try:
                                root = ET.fromstring(content)
                                for elem in root.iter():
                                    if elem.text:
                                        t = elem.text.strip()
                                        if t:
                                            texts.append(t)
                                    if elem.tail:
                                        t = elem.tail.strip()
                                        if t:
                                            texts.append(t)
                            except ET.ParseError:
                                continue
                return '\n'.join(texts)
            except Exception as e:
                logger.warning(f"OFD 文本提取失败: {e}")
                return ""

        return ""

    # ── 正则匹配辅助 ────────────────────────────────────────────

    @staticmethod
    def _is_regex_truncated(pattern: str) -> bool:
        """检测正则是否被截断（语法不完整）"""
        if not pattern:
            return False
        # 末尾以 | 结尾：交替未完成
        if pattern.rstrip().endswith('|'):
            return True
        # 末尾以未闭合的 (?: 开头或包含未闭合分组
        # 统计括号层级
        depth = 0
        i = 0
        while i < len(pattern):
            ch = pattern[i]
            if ch == '\\':
                i += 2  # 跳过转义字符
                continue
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                # 如果括号深度为负，说明有多余的 )
                # 但要容忍字符类中的 )
            elif ch == '[':
                # 跳过字符类
                i += 1
                while i < len(pattern) and pattern[i] != ']':
                    if pattern[i] == '\\':
                        i += 1
                    i += 1
            i += 1
        # 括号未闭合、或深度异常（括号不匹配）
        if depth != 0:
            return True
        # 末尾以未闭合的字符类开头
        if pattern.rstrip().endswith('['):
            return True
        return False

    @staticmethod
    def _apply_regex_patterns(patterns: dict, text: str) -> dict:
        """
        用正则字典从文本中提取字段值

        Args:
            patterns: {字段名: 正则字符串}，每个正则必须有捕获组
            text: 原始文本

        Returns:
            dict: {字段名: 提取的值}
        """
        result = {}
        for field, pattern in patterns.items():
            if not pattern:
                result[field] = ""
                continue

            # 预检：正则是否被截断
            if AIService._is_regex_truncated(pattern):
                logger.warning(
                    f"[正则应用] 字段 {field}: 正则疑似被截断（括号/交替不完整），"
                    f"跳过使用，完整内容: {pattern}"
                )
                result[field] = ""
                continue

            try:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    if match.groups():
                        value = match.group(1).strip()
                    else:
                        value = match.group(0).strip()
                    result[field] = value
                else:
                    result[field] = ""
            except re.error as e:
                logger.warning(
                    f"[正则应用] 字段 {field}: 无效正则 (re.error={e})，"
                    f"完整内容: {pattern}"
                )
                result[field] = ""
        return result

    @staticmethod
    def _fix_amount_extraction(extracted: dict, text: str) -> dict:
        """
        智能修正金额字段提取错误

        处理常见问题：
        1. tax_amount 错误等于 amount_without_tax（合 计 行两个金额混淆）
        2. total_amount 为空或为 0（价税合计未提取到）

        Args:
            extracted: _apply_regex_patterns 返回的原始提取结果
            text: 发票原始文本

        Returns:
            dict: 修正后的提取结果
        """
        import re as _re

        amt = extracted.get('amount_without_tax', '')
        tax = extracted.get('tax_amount', '')
        total = extracted.get('total_amount', '')

        # ── 修正1: tax_amount 错误等于 amount_without_tax ──
        if amt and tax and amt == tax:
            logger.debug(
                f"[金额修正] 检测到 tax_amount({tax}) == amount_without_tax({amt})，"
                f"尝试从合 计 行重新提取"
            )
            # 从 合 计 ¥A ¥B 行提取第二个金额作为税额
            m = _re.search(r'合\s*计\s*¥([\d.]+)\s*¥([\d.]+)', text)
            if m:
                extracted['amount_without_tax'] = m.group(1)
                extracted['tax_amount'] = m.group(2)
                logger.debug(
                    f"[金额修正] 合 计 行重新提取: "
                    f"不含税={m.group(1)}, 税额={m.group(2)}"
                )
            else:
                # 备选：匹配 "合 计 ¥金额" 后紧跟的第二个 ¥金额
                m = _re.search(
                    r'合\s*计[\s\S]*?¥([\d.]+)[\s\S]*?¥([\d.]+)', text
                )
                if m:
                    extracted['amount_without_tax'] = m.group(1)
                    extracted['tax_amount'] = m.group(2)
                    logger.debug(
                        f"[金额修正] 合 计 行(宽松)重新提取: "
                        f"不含税={m.group(1)}, 税额={m.group(2)}"
                    )

        # ── 修正2: total_amount 为空或为 0 ──
        total = extracted.get('total_amount', '')
        is_total_missing = (
            not total
            or total == '0'
            or total == '0.0'
            or total == '0.00'
        )
        if is_total_missing:
            # 尝试从 价税合计 或 小写 行提取
            m = _re.search(
                r'(?:价税合计|小写)[\s\S]*?¥\s*([\d.]+)', text
            )
            if m:
                extracted['total_amount'] = m.group(1)
                logger.debug(
                    f"[金额修正] 价税合计重新提取: {m.group(1)}"
                )
            else:
                # 如果还是没有，且不含税和税额都有值，则计算
                amt_val = extracted.get('amount_without_tax', '')
                tax_val = extracted.get('tax_amount', '')
                if amt_val and tax_val:
                    try:
                        calc_total = float(amt_val) + float(tax_val)
                        extracted['total_amount'] = f"{calc_total:.2f}"
                        logger.debug(
                            f"[金额修正] 价税合计计算得出: "
                            f"{amt_val} + {tax_val} = {calc_total:.2f}"
                        )
                    except ValueError:
                        pass

        # ── 修正3: amount_without_tax 为空但其他金额存在 ──
        amt = extracted.get('amount_without_tax', '')
        tax = extracted.get('tax_amount', '')
        total = extracted.get('total_amount', '')
        is_amt_missing = (
            not amt or amt == '0' or amt == '0.0' or amt == '0.00'
        )
        if is_amt_missing:
            # 尝试从合 计 行第一个 ¥ 提取
            m = _re.search(r'合\s*计\s*¥([\d.]+)', text)
            if m:
                extracted['amount_without_tax'] = m.group(1)
                logger.debug(
                    f"[金额修正] 不含税金额重新提取: {m.group(1)}"
                )
            elif total and tax:
                try:
                    calc_amt = float(total) - float(tax)
                    if calc_amt > 0:
                        extracted['amount_without_tax'] = f"{calc_amt:.2f}"
                        logger.debug(
                            f"[金额修正] 不含税金额计算得出: "
                            f"{total} - {tax} = {calc_amt:.2f}"
                        )
                except ValueError:
                    pass

        # ── 修正4: total_amount 与非零的 amount_without_tax+tax_amount 不一致 ──
        try:
            amt_val = float(extracted.get('amount_without_tax', 0) or 0)
            tax_val = float(extracted.get('tax_amount', 0) or 0)
            total_val = float(extracted.get('total_amount', 0) or 0)
        except (ValueError, TypeError):
            amt_val = tax_val = total_val = 0.0

        if amt_val > 0 and total_val > 0:
            expected = amt_val + tax_val
            if abs(total_val - expected) > 0.02:
                # 尝试从文本中重新提取价税合计
                m = _re.search(
                    r'(?:价税合计|小写)[\s\S]*?[¥￥]\s*([\d.]+)', text
                )
                if m:
                    extracted['total_amount'] = m.group(1)
                    logger.debug(
                        f"[金额修正] total_amount 不一致({total_val})，"
                        f"重新提取: {m.group(1)} (期望={expected:.2f})"
                    )
                else:
                    # 回退：直接用 amount_without_tax + tax_amount 计算
                    extracted['total_amount'] = f"{expected:.2f}"
                    logger.debug(
                        f"[金额修正] total_amount 不一致({total_val})，"
                        f"计算得出: {expected:.2f}"
                    )

        return extracted

    @staticmethod
    def _fix_name_extraction(extracted: dict, text: str) -> dict:
        """
        智能修正购买方/销售方名称提取错误

        常见问题：AI 为 buyer_name 和 seller_name 生成了相同的正则，
        导致两者都匹配到文本中第一个公司名（购买方）。

        修正策略：
        1. 如果 buyer_name == seller_name，用 findall 找出所有公司名，
           第一个→购买方，最后一个→销售方
        2. 如果 buyer_name 为空，尝试找第一个公司名
        3. 如果 seller_name 为空，尝试找最后一个公司名
        """
        import re as _re

        buyer = extracted.get('buyer_name', '')
        seller = extracted.get('seller_name', '')

        # 公司名称正则：涵盖常见企业类型
        # 匹配：中文名+公司后缀 或 中文名+（个体工商户）等
        company_suffix = (
            r'(?:有限(?:责任)?公司|股份有限公司|有限责任公司)'
            r'|(?:合伙|个人|个体)企业[）)]?'
            r'|个体工商户[）)]?'
            r'|分公司'
            r'|(?:酒店|宾馆|餐饮|餐厅|烧烤店|饭店|旅馆|客栈)'
            r'|(?:中心|经营部|服务部|营业部|办事处)'
            r'|(?:集团|实业|控股|投资|贸易|科技|信息|咨询|管理|服务)'
            r'(?:有限(?:责任)?公司|股份有限公司|有限责任公司)?'
        )
        # 更宽松的匹配：含中文4字符以上 + 公司后缀
        full_pattern = (
            r'[\u4e00-\u9fa5（）()\u3008-\u300f]{4,}'
            r'(?:' + company_suffix + r')'
        )

        all_companies = _re.findall(full_pattern, text)

        # 过滤掉明显不是主体的（税务局、银行分支、印章文字等）
        skip_keywords = [
            '国家税务总局', '税务局', '信用合作社',
            '监制', '印章', '全国', '统一',
            # 银行/金融机构（非公司主体，含"银行"字样的都是金融机构）
            '银行', '开户行',
        ]
        # 额外过滤：匹配项若以银行缩写开头且以支行/分行结尾，跳过
        bank_prefix = _re.compile(
            r'^(?:中国|工行|农行|建行|中行|招行|交行|邮储|浦发|兴业|民生|光大|华夏|中信|平安)'
            r'|^(?:工商银行|农业银行|建设银行|中国银行|招商银行|交通银行)'
        )

        companies = []
        for c in all_companies:
            if any(kw in c for kw in skip_keywords):
                continue
            # 跳过银行分支
            if bank_prefix.match(c):
                continue
            # 去重（保持顺序）
            if c not in companies:
                companies.append(c)

        logger.debug(
            f"[名称修正] 提取到 {len(companies)} 个候选公司名: {companies}"
        )

        # ── 修正 buyer_name ──
        buyer = extracted.get('buyer_name', '')
        if not buyer and companies:
            extracted['buyer_name'] = companies[0]
            logger.debug(
                f"[名称修正] buyer_name 为空，取第一个: {companies[0]}"
            )

        # ── 修正 seller_name ──
        seller = extracted.get('seller_name', '')
        if not seller and len(companies) >= 2:
            extracted['seller_name'] = companies[-1]
            logger.debug(
                f"[名称修正] seller_name 为空，取最后一个: {companies[-1]}"
            )

        # ── 修正 buyer == seller（两者相同且非空）──
        buyer = extracted.get('buyer_name', '')
        seller = extracted.get('seller_name', '')
        if buyer and seller and buyer == seller and len(companies) >= 2:
            extracted['buyer_name'] = companies[0]
            extracted['seller_name'] = companies[-1]
            logger.debug(
                f"[名称修正] buyer==seller=={buyer}，"
                f"重新分配: buyer={companies[0]}, seller={companies[-1]}"
            )
        elif buyer and seller and buyer == seller and len(companies) == 1:
            # 只有一个公司名的情况：它可能是销售方（如小商户发票）
            # 保留 buyer_name，seller_name 也保留（可能是同一家公司开票给自己）
            logger.debug(
                f"[名称修正] 仅一个公司名({buyer})，可能是同一主体"
            )

        # ── 修正 seller_name 不在候选列表中（AI 匹配到银行支行等碎片）──
        buyer = extracted.get('buyer_name', '')
        seller = extracted.get('seller_name', '')
        if seller and len(companies) >= 2 and seller not in companies:
            # seller 不在候选公司列表中，说明匹配到了文本末尾的碎片（银行支行等）
            # 用 findall 找到的最后一个公司名替换
            extracted['seller_name'] = companies[-1]
            logger.debug(
                f"[名称修正] seller_name='{seller}' 不在候选列表中，"
                f"替换为最后一个候选: {companies[-1]}"
            )
        # 同理检查 buyer_name
        if buyer and len(companies) >= 1 and buyer not in companies:
            extracted['buyer_name'] = companies[0]
            logger.debug(
                f"[名称修正] buyer_name='{buyer}' 不在候选列表中，"
                f"替换为第一个候选: {companies[0]}"
            )

        return extracted

    # ── 公共方法 ────────────────────────────────────────────────

    def test_connection(self) -> tuple:
        config = self.get_config()
        if not config.api_url:
            return False, "API 地址未配置"
        if not config.api_key:
            return False, "API Key 未配置"

        try:
            messages = [{"role": "user", "content": "请回复'连接成功'四个字。"}]
            result = self._call_api(messages, use_json_format=False, return_raw=True)
            reply = result.get("text", "")
            logger.info(f"AI 连接测试成功: {config.api_url}, 模型: {config.model_name}")
            return True, f"连接成功，模型: {config.model_name}"
        except AIServiceError as e:
            return False, str(e)
        except Exception as e:
            logger.error(f"AI 连接测试失败: {e}")
            return False, f"连接失败: {e}"

    def analyze_invoice(self, file_path: str) -> dict:
        """
        使用 AI 分析发票

        流程：
        1. 提取文件原始文本
        2. 将文本发给 AI，要求 AI 返回各字段的正则表达式
        3. 本地用 AI 返回的正则从原始文本提取字段值
        4. 返回提取结果

        Returns:
            dict: 提取的发票信息
        """
        logger.info(f"AI 分析发票: {file_path}")

        text = self._extract_text_for_ai(file_path)
        if not text.strip():
            raise AIServiceError("无法从文件中提取任何文本内容")

        filename = Path(file_path).name
        logger.info(f"[发票识别] 原始源文本: {filename} ({len(text)} 字符)\n{text}")

        if len(text) > 8000:
            logger.warning(f"文件文本过长（{len(text)} 字符），已截断为 8000")
            text = text[:8000]

        # 步骤1: 让 AI 生成正则表达式
        messages = self._build_analyze_messages(text, file_path)

        try:
            ai_regex_result = self._call_api(messages)
        except AIServiceError as e:
            if "__retry_no_json_format__" in str(e):
                ai_regex_result = self._call_api(messages, use_json_format=False)
            else:
                raise

        # 步骤2: 用 AI 返回的正则在原始文本上提取
        patterns = ai_regex_result.get("patterns", ai_regex_result)
        extracted = self._apply_regex_patterns(patterns, text)

        # 步驟2.5: 智能修正金额字段提取错误（税额混淆、价税合计缺失等）
        extracted = self._fix_amount_extraction(extracted, text)

        # 步骤2.6: 智能修正购买方/销售方名称（两者相同时用findall重提取）
        extracted = self._fix_name_extraction(extracted, text)

        # 步骤3: 后处理
        result = self._postprocess_invoice_data(extracted)
        # 把 AI 返回的额外字段也带上
        for key in ('invoice_type', 'business_type', 'confidence'):
            val = ai_regex_result.get(key, '')
            if val:
                result[key] = val

        logger.info(f"AI 分析完成: 发票号码={result.get('invoice_number', '')}")
        return result

    def _build_analyze_messages(self, text: str, file_path: str) -> list:
        """构建发票分析消息 — AI 返回正则表达式"""
        ext = Path(file_path).suffix.lower().lstrip('.')

        system_prompt = (
            "你是一个中国发票信息提取专家。"
            "请分析用户提供的发票文本，为以下7个字段各编写一个 Python 正则表达式。"
            "严格以 JSON 格式返回，不要输出 JSON 之外的内容。"
        )

        fields_desc = (
            "请为以下7个字段各生成一个 Python 正则表达式（re 模块语法）：\n\n"
            "1. invoice_number: 发票号码（如 12345678 或 12345678901234567890）\n"
            "2. invoice_date: 开票日期（如 2024年01月15日 或 2024-01-15）\n"
            "3. buyer_name: 购买方名称（公司全称）\n"
            "4. seller_name: 销售方名称（公司全称）\n"
            "5. amount_without_tax: 合计金额/不含税金额（如 ¥1,234.56）\n"
            "6. tax_amount: 合计税额（如 ¥56.78）\n"
            "7. total_amount: 价税合计/小写金额（如 ¥1,291.34）\n\n"
            "⚠️ PDF 文本布局重要说明（左右分栏式布局）：\n"
            "- 文本由 pdfplumber 从 PDF 中原始提取，保留视觉列位置\n"
            "- 中国电子发票采用左右分栏布局：字段标签在左栏，值在右栏\n"
            "- 提取后标签（如 '发票号码：'）和值（如 '26112000001979557951'）可能相距很远，\n"
            "  中间隔着大量其他文本行（如印章、监制章、税务局名称等）\n"
            "- 因此，正则不能依赖标签紧邻值来匹配，需要用更灵活的跨行策略\n"
            "- 公司名称（购买方/销售方）会出现在文本中的公司全称位置（通常靠近统一社会信用代码），\n"
            "  而非紧挨 '名称：' 标签\n\n"
            "正则编写要求：\n"
            "- 每个正则必须包含一个捕获组 () 用于提取目标值\n"
            "- 使用 [\\s\\S]*? 而非 .*? 来跨行匹配（因为 PDF 提取的文本含换行）\n"
            "- 发票号码：不要依赖 '发票号码：' 标签，直接用长数字模式匹配（如 (\\d{8,20})），\n"
            "  文本中最长的连续数字串通常是发票号码\n"
            "- 开票日期：使用日期模式匹配（如 (\\d{4}年\\d{1,2}月\\d{1,2}日)），不依赖 '开票日期：' 标签\n"
            "- 购买方/销售方名称：两者必须用不同的正则！\n"
            "  * buyer_name：匹配文本中**第一个**出现的公司全称（购买方排前面）。\n"
            "    如 ([\\u4e00-\\u9fa5()（）]{4,}(?:有限公司|...)) 即可匹配第一个公司名\n"
            "  * seller_name：销售方名称在文本**中间位置**（统一社会信用代码附近），\n"
            "    而非文本末尾。文本末尾的备注区域通常包含银行名等无关信息。\n"
            "    策略：定位销售方统一社会信用代码（18位数字字母），\n"
            "    然后在其附近（前后50字符）匹配公司全称。\n"
            "    如 \\d{18}[\\s\\S]{0,50}?([\\u4e00-\\u9fa5()（）]{4,}(?:有限公司|...))\n"
            "  * 公司后缀包括：有限公司、有限责任公司、股份有限公司、合伙企业、个体工商户、\n"
            "    分公司、酒店、宾馆、餐饮、餐厅、烧烤店、中心、经营部 等\n"
            "  * ⚠️ 全角括号完整性：公司名称如「XX（个体工商户）」，\n"
            "    闭括号 ）是名称的一部分，必须完整捕获。\n"
            "    若名称中含（则必定有配对的），正则不可在 ）前截断。\n"
            "  * ⚠️ 重要：银行、支行、分行、信用社等金融机构名称**不是**公司主体，\n"
            "    绝对不要匹配！不要把含「银行」「支行」「分行」「信用社」的名称作为销售方。\n"
            "  * 不依赖 '名称：' 标签\n"
            "- '合 计' 行格式为 '合 计 ¥不含税金额 ¥税额'：\n"
            "  amount_without_tax 匹配合行第一个 ¥ 后的数字\n"
            "  tax_amount 匹配合行第二个 ¥ 后的数字（务必将二者区分开！）\n"
            "- 价税合计：匹配 '价税合计' 或 '小写' 后的 ¥ 数字（提示：¥ 和数字之间可能有空格，"
            "  且标签和 ¥ 之间可能隔着大写金额、括号等内容，请用 [\\s\\S]*? 跨行匹配）\n"
            "- 金额字段只提取数字和小数点，不要带 ¥ 符号和逗号\n"
            "- 正则必须语法完整：所有 () 括号必须配对闭合，交替组 | 不可悬空结尾\n"
            "- 每个正则控制在 200 字符以内，避免过长导致截断\n"
            "- 如果某字段在文本中找不到，返回空字符串 ''\n\n"
            "返回 JSON 格式：\n"
            "{\n"
            '  "patterns": {\n'
            '    "invoice_number": "正则表达式1",\n'
            '    "invoice_date": "正则表达式2",\n'
            '    "buyer_name": "正则表达式3",\n'
            '    "seller_name": "正则表达式4",\n'
            '    "amount_without_tax": "正则表达式5",\n'
            '    "tax_amount": "正则表达式6",\n'
            '    "total_amount": "正则表达式7"\n'
            '  },\n'
            '  "invoice_type": "发票类型（电子发票/增值税专票/增值税普票/机打发票/定额发票/其他）",\n'
            '  "business_type": "业务类型（餐饮/住宿/交通/办公/购物/其他）",\n'
            '  "confidence": "high/medium/low"\n'
            "}"
        )

        user_prompt = (
            f"{fields_desc}\n\n"
            f"文件格式: {ext}\n"
            f"发票文本：\n---\n{text}\n---"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def learn_format(self, file_path: str, error_context: str = "") -> dict:
        """
        AI 学习新的发票格式

        让 AI 分析发票文本，返回 extraction_config（正则字典）和规则元信息。

        Returns:
            dict: {
                "extraction_config": {field: pattern, ...},
                "rule_name": "...",
                "match_keywords": [...]
            }
        """
        logger.info(f"AI 学习发票格式: {file_path}"
                    + (" (修正模式)" if error_context else ""))

        ext = Path(file_path).suffix.lower()
        file_format = ext.lstrip('.')
        messages = self._build_learn_messages(file_path, file_format, error_context)

        try:
            result = self._call_api(messages, temperature=0.2)
        except AIServiceError as e:
            if "__retry_no_json_format__" in str(e):
                result = self._call_api(messages, temperature=0.2, use_json_format=False)
            else:
                raise

        extraction_config = result.get("extraction_config", result.get("patterns", {}))
        # 确保值是纯正则字符串
        clean_config = {}
        for field, pattern in extraction_config.items():
            if isinstance(pattern, dict):
                clean_config[field] = pattern.get('pattern', '')
            else:
                clean_config[field] = pattern

        rule_name = result.get("rule_name", "未命名规则")
        match_keywords = result.get("match_keywords", [])
        if isinstance(match_keywords, str):
            match_keywords = [match_keywords]

        logger.info(
            f"AI 学习完成: 规则名={rule_name}, "
            f"关键词={match_keywords}, 字段数={len(clean_config)}"
        )

        return {
            "extraction_config": clean_config,
            "rule_name": rule_name,
            "match_keywords": match_keywords,
        }

    def _build_learn_messages(self, file_path: str, file_format: str,
                              error_context: str = "") -> list:
        """构建 AI 学习消息 — 要求返回正则表达式提取配置"""
        text = self._extract_text_for_ai(file_path)
        if not text.strip():
            raise AIServiceError("无法从文件中提取任何文本内容")

        if len(text) > 8000:
            text = text[:8000]

        system_prompt = (
            "你是一个发票解析规则设计专家。请分析用户提供的发票文本，"
            "为每个关键字段编写 Python 正则表达式。严格以 JSON 格式返回。"
        )

        learn_instructions = (
            "请分析以下发票文本，完成以下任务：\n\n"
            "**为以下7个字段各生成一个 Python 正则表达式**：\n"
            "1. invoice_number: 发票号码\n"
            "2. invoice_date: 开票日期\n"
            "3. buyer_name: 购买方名称\n"
            "4. seller_name: 销售方名称\n"
            "5. amount_without_tax: 合计金额/不含税金额\n"
            "6. tax_amount: 合计税额\n"
            "7. total_amount: 价税合计/小写金额\n\n"
            "⚠️ PDF 文本布局重要说明（左右分栏式布局）：\n"
            "- 文本由 pdfplumber 从 PDF 中原始提取，保留视觉列位置\n"
            "- 中国电子发票采用左右分栏布局：字段标签在左栏，值在右栏\n"
            "- 提取后标签（如 '发票号码：'）和值（如 '26112000001979557951'）可能相距很远，\n"
            "  中间隔着大量其他文本行（如印章、监制章、税务局名称等）\n"
            "- 因此，正则不能依赖标签紧邻值来匹配，需要用更灵活的跨行策略\n"
            "- 公司名称（购买方/销售方）会出现在文本中的公司全称位置（通常靠近统一社会信用代码），\n"
            "  而非紧挨 '名称：' 标签\n\n"
            "正则编写要求：\n"
            "- 使用 Python re 模块语法\n"
            "- 每个正则必须包含一个捕获组 () 用于提取目标值\n"
            "- 使用 [\\s\\S]*? 跨越换行（PDF 文本含换行符）\n"
            "- 使用 \\s* 匹配字段标签中可能的空格\n"
            "- 发票号码：不要依赖 '发票号码：' 标签，直接用长数字模式匹配（如 (\\d{8,20})），\n"
            "  文本中最长的连续数字串通常是发票号码\n"
            "- 开票日期：使用日期模式匹配（如 (\\d{4}年\\d{1,2}月\\d{1,2}日)），不依赖 '开票日期：' 标签\n"
            "- 购买方/销售方名称：两者必须用不同的正则！\n"
            "  * buyer_name：匹配文本中**第一个**出现的公司全称（购买方排前面）。\n"
            "    如 ([\\u4e00-\\u9fa5()（）]{4,}(?:有限公司|...)) 即可匹配第一个公司名\n"
            "  * seller_name：销售方名称在文本**中间位置**（统一社会信用代码附近），\n"
            "    而非文本末尾。文本末尾的备注区域通常包含银行名等无关信息。\n"
            "    策略：定位销售方统一社会信用代码（18位数字字母），\n"
            "    然后在其附近（前后50字符）匹配公司全称。\n"
            "    如 \\d{18}[\\s\\S]{0,50}?([\\u4e00-\\u9fa5()（）]{4,}(?:有限公司|...))\n"
            "  * 公司后缀包括：有限公司、有限责任公司、股份有限公司、合伙企业、个体工商户、\n"
            "    分公司、酒店、宾馆、餐饮、餐厅、烧烤店、中心、经营部 等\n"
            "  * ⚠️ 全角括号完整性：公司名称如「XX（个体工商户）」，\n"
            "    闭括号 ）是名称的一部分，必须完整捕获。\n"
            "    若名称中含（则必定有配对的），正则不可在 ）前截断。\n"
            "  * ⚠️ 重要：银行、支行、分行、信用社等金融机构名称**不是**公司主体，\n"
            "    绝对不要匹配！不要把含「银行」「支行」「分行」「信用社」的名称作为销售方。\n"
            "  * 不依赖 '名称：' 标签\n"
            "- '合 计' 行格式为 '合 计 ¥不含税金额 ¥税额'：\n"
            "  amount_without_tax 匹配合行第一个 ¥ 后的数字\n"
            "  tax_amount 匹配合行第二个 ¥ 后的数字（务必将二者区分开！）\n"
            "- 价税合计：匹配 '价税合计' 或 '小写' 后的 ¥ 数字（提示：¥ 和数字之间可能有空格，"
            "  且标签和 ¥ 之间可能隔着大写金额、括号等内容，请用 [\\s\\S]*? 跨行匹配）\n"
            "- 金额只捕获数字和小数点\n"
            "- 正则必须语法完整：所有 () 括号必须配对闭合，交替组 | 不可悬空结尾\n"
            "- 每个正则控制在 200 字符以内，避免过长导致截断\n\n"
            "同时提供：\n"
            "- rule_name: 简短规则名称（建议用销售方名称）\n"
            "- match_keywords: 3-5个匹配关键词（用于快速识别同类发票）\n\n"
            "返回 JSON 格式：\n"
            "{\n"
            '  "extraction_config": {\n'
            '    "invoice_number": "正则1",\n'
            '    "invoice_date": "正则2",\n'
            '    "buyer_name": "正则3",\n'
            '    "seller_name": "正则4",\n'
            '    "amount_without_tax": "正则5",\n'
            '    "tax_amount": "正则6",\n'
            '    "total_amount": "正则7"\n'
            '  },\n'
            '  "rule_name": "规则名称",\n'
            '  "match_keywords": ["关键词1", "关键词2", "关键词3"]\n'
            "}"
        )

        user_prompt = (
            f"{learn_instructions}\n\n"
            f"文件格式: {file_format}\n"
            f"发票文本：\n---\n{text}\n---"
        )

        if error_context:
            user_prompt += (
                f"\n\n【‼️ 上次正则提取失败，请修正】\n"
                f"以下字段的正则表达式未能正确提取：\n"
                f"{error_context}\n\n"
                f"请仔细检查发票原文，修正对应的正则表达式。"
            )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    # ── 后处理 ──────────────────────────────────────────────────

    @staticmethod
    def _postprocess_invoice_data(data: dict) -> dict:
        """对提取的发票数据进行后处理"""
        for field in ('amount_without_tax', 'tax_amount', 'total_amount'):
            val = data.get(field, 0)
            if isinstance(val, str):
                data[field] = parse_amount(val)
            elif isinstance(val, (int, float)):
                data[field] = float(val)
            else:
                data[field] = 0.0

        date_val = data.get('invoice_date', '')
        if isinstance(date_val, str) and date_val:
            normalized = normalize_date(date_val)
            if normalized:
                data['invoice_date'] = normalized

        inv_no = data.get('invoice_number', '')
        if isinstance(inv_no, (int, float)):
            data['invoice_number'] = str(int(inv_no))
        elif not isinstance(inv_no, str):
            data['invoice_number'] = str(inv_no)

        # 金额校验
        amount = data.get('amount_without_tax', 0)
        tax = data.get('tax_amount', 0)
        total = data.get('total_amount', 0)

        if amount > 0 and tax >= 0 and total > 0:
            expected = amount + tax
            diff = abs(total - expected)
            if diff > 0.02:
                # 自动修正 total_amount 为 amount_without_tax + tax_amount
                corrected_total = round(expected, 2)
                data['total_amount'] = corrected_total
                data['validation_warning'] = (
                    f"金额校验不一致，已自动修正: {amount} + {tax} = {expected}，"
                    f"原价税合计为 {total}，差额 {diff:.2f}"
                )
                logger.debug(
                    f"[金额修正] _postprocess 自动修正 total_amount: "
                    f"{total} → {corrected_total}"
                )

        return data


# 全局 AI 服务实例
ai_service = AIService()
