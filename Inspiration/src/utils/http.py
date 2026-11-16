"""
Robust HTTP helper med retries, exponential backoff, rate limit håndtering, timeout og logging.
Genbrugt fra tx-lite projektet.
"""

import logging
import time
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HTTPClient:
    """
    Robust HTTP klient med retry logik, exponential backoff, rate limit håndtering og logging.
    
    Eksempel:
        client = HTTPClient(logger=my_logger)
        response = client.get("https://api.example.com/data", params={"key": "value"})
        data = response.json()
    """
    
    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        timeout: float = 60.0,
        respect_retry_after: bool = True,
    ):
        """
        Args:
            logger: Logger instance (optional, hvis None bruges standard logging)
            max_retries: Maksimalt antal retries (default: 3)
            backoff_factor: Faktor for exponential backoff i sekunder (default: 1.0)
            timeout: Request timeout i sekunder (default: 60.0)
            respect_retry_after: Respekter Retry-After header ved 429 (default: True)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.respect_retry_after = respect_retry_after
        
        # Opret session med retry strategy
        self.session = requests.Session()
        
        # Retry strategy for 5xx errors og connection errors
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[500, 502, 503, 504],  # Server errors
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
            raise_on_status=False,  # Vi håndterer status codes selv
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _get_retry_after(self, response: requests.Response) -> Optional[float]:
        """
        Henter Retry-After header fra response (ved 429 Too Many Requests).
        
        Returns:
            Antal sekunder at vente, eller None hvis ikke sat
        """
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                self.logger.warning("Retry-After header er ikke et tal: %s", retry_after)
        return None
    
    def _handle_rate_limit(self, response: requests.Response, attempt: int) -> bool:
        """
        Håndterer 429 Too Many Requests med exponential backoff.
        
        Args:
            response: HTTP response med 429 status
            attempt: Nuværende retry attempt nummer
        
        Returns:
            True hvis vi skal retry, False hvis vi skal give op
        """
        if response.status_code != 429:
            return False
        
        if attempt >= self.max_retries:
            self.logger.error(
                "Rate limit (429) efter %d forsøg. Giver op.",
                attempt
            )
            return False
        
        # Hent Retry-After hvis tilgængelig
        wait_time = self._get_retry_after(response)
        
        if wait_time is None:
            # Exponential backoff: 2^attempt * backoff_factor
            wait_time = (2 ** attempt) * self.backoff_factor
        
        self.logger.warning(
            "Rate limit (429) - venter %.1f sekunder før retry %d/%d",
            wait_time,
            attempt + 1,
            self.max_retries
        )
        
        time.sleep(wait_time)
        return True
    
    def _log_request(self, method: str, url: str, **kwargs):
        """Logger request detaljer."""
        params = kwargs.get("params") or {}
        # Fjern sensitive data fra logging (fx passwords, API keys)
        safe_params = {}
        if params and isinstance(params, dict):
            safe_params = {
                k: "***" if any(sensitive in k.lower() for sensitive in ["password", "api_key", "apikey", "appid"]) 
                else v 
                for k, v in params.items()
            }
        self.logger.debug(
            "HTTP %s: %s (params: %s, timeout: %.1fs)",
            method,
            url,
            safe_params,
            kwargs.get("timeout", self.timeout)
        )
    
    def _log_response(self, response: requests.Response, duration: float):
        """Logger response detaljer."""
        self.logger.debug(
            "HTTP Response: %s %s (status: %d, duration: %.2fs, size: %d bytes)",
            response.request.method,
            response.url,
            response.status_code,
            duration,
            len(response.content)
        )
    
    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> requests.Response:
        """
        HTTP GET request med retry logik og rate limit håndtering.
        
        Args:
            url: Request URL
            params: Query parameters
            headers: HTTP headers
            timeout: Request timeout (overrides default)
            **kwargs: Yderligere arguments til requests.get()
        
        Returns:
            requests.Response object
        
        Raises:
            requests.HTTPError: Hvis request fejler efter alle retries
            requests.Timeout: Hvis request timeout
            requests.ConnectionError: Hvis connection fejler
        """
        timeout = timeout or self.timeout
        attempt = 0
        
        self._log_request("GET", url, params=params, timeout=timeout)
        start_time = time.time()
        
        while attempt <= self.max_retries:
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                    **kwargs
                )
                
                duration = time.time() - start_time
                self._log_response(response, duration)
                
                # Håndter rate limiting (429)
                if response.status_code == 429:
                    if self._handle_rate_limit(response, attempt):
                        attempt += 1
                        start_time = time.time()
                        continue
                    else:
                        response.raise_for_status()
                
                # Håndter andre fejl
                if not response.ok:
                    self.logger.warning(
                        "HTTP %d: %s (attempt %d/%d)",
                        response.status_code,
                        response.url,
                        attempt + 1,
                        self.max_retries + 1
                    )
                    
                    # Retry på 5xx errors
                    if 500 <= response.status_code < 600 and attempt < self.max_retries:
                        wait_time = (2 ** attempt) * self.backoff_factor
                        self.logger.info(
                            "Server error - venter %.1f sekunder før retry",
                            wait_time
                        )
                        time.sleep(wait_time)
                        attempt += 1
                        start_time = time.time()
                        continue
                
                # Success
                if attempt > 0:
                    self.logger.info(
                        "Request successful efter %d retry(ies)",
                        attempt
                    )
                
                return response
                
            except requests.Timeout as e:
                attempt += 1
                if attempt > self.max_retries:
                    self.logger.error("Request timeout efter %d forsøg", attempt)
                    raise
                
                wait_time = (2 ** attempt) * self.backoff_factor
                self.logger.warning(
                    "Request timeout - venter %.1f sekunder før retry %d/%d",
                    wait_time,
                    attempt + 1,
                    self.max_retries + 1
                )
                time.sleep(wait_time)
                start_time = time.time()
                
            except requests.ConnectionError as e:
                attempt += 1
                if attempt > self.max_retries:
                    self.logger.error("Connection error efter %d forsøg: %s", attempt, str(e))
                    raise
                
                wait_time = (2 ** attempt) * self.backoff_factor
                self.logger.warning(
                    "Connection error - venter %.1f sekunder før retry %d/%d: %s",
                    wait_time,
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )
                time.sleep(wait_time)
                start_time = time.time()
        
        # Hvis vi når her, er noget galt
        raise requests.HTTPError(f"Request fejlede efter {self.max_retries + 1} forsøg")
    
    def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> requests.Response:
        """
        HTTP POST request med retry logik og rate limit håndtering.
        
        Args:
            url: Request URL
            json: JSON data to send (will be serialized)
            data: Form data to send
            params: Query parameters
            headers: HTTP headers
            timeout: Request timeout (overrides default)
            **kwargs: Yderligere arguments til requests.post()
        
        Returns:
            requests.Response object
        """
        timeout = timeout or self.timeout
        attempt = 0
        
        self._log_request("POST", url, params=params, timeout=timeout)
        start_time = time.time()
        
        while attempt <= self.max_retries:
            try:
                response = self.session.post(
                    url,
                    json=json,
                    data=data,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                    **kwargs
                )
                
                duration = time.time() - start_time
                self._log_response(response, duration)
                
                # Håndter rate limiting (429)
                if response.status_code == 429:
                    if self._handle_rate_limit(response, attempt):
                        attempt += 1
                        start_time = time.time()
                        continue
                    else:
                        response.raise_for_status()
                
                # Håndter andre fejl
                if not response.ok:
                    self.logger.warning(
                        "HTTP %d: %s (attempt %d/%d)",
                        response.status_code,
                        response.url,
                        attempt + 1,
                        self.max_retries + 1
                    )
                    
                    # Retry på 5xx errors
                    if 500 <= response.status_code < 600 and attempt < self.max_retries:
                        wait_time = (2 ** attempt) * self.backoff_factor
                        self.logger.info(
                            "Server error - venter %.1f sekunder før retry",
                            wait_time
                        )
                        time.sleep(wait_time)
                        attempt += 1
                        start_time = time.time()
                        continue
                
                # Success
                if attempt > 0:
                    self.logger.info(
                        "Request successful efter %d retry(ies)",
                        attempt
                    )
                
                return response
                
            except requests.Timeout as e:
                attempt += 1
                if attempt > self.max_retries:
                    self.logger.error("Request timeout efter %d forsøg", attempt)
                    raise
                
                wait_time = (2 ** attempt) * self.backoff_factor
                self.logger.warning(
                    "Request timeout - venter %.1f sekunder før retry %d/%d",
                    wait_time,
                    attempt + 1,
                    self.max_retries + 1
                )
                time.sleep(wait_time)
                start_time = time.time()
                
            except requests.ConnectionError as e:
                attempt += 1
                if attempt > self.max_retries:
                    self.logger.error("Connection error efter %d forsøg: %s", attempt, str(e))
                    raise
                
                wait_time = (2 ** attempt) * self.backoff_factor
                self.logger.warning(
                    "Connection error - venter %.1f sekunder før retry %d/%d: %s",
                    wait_time,
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )
                time.sleep(wait_time)
                start_time = time.time()
        
        # Hvis vi når her, er noget galt
        raise requests.HTTPError(f"Request fejlede efter {self.max_retries + 1} forsøg")
    
    def close(self):
        """Lukker HTTP session."""
        self.session.close()

