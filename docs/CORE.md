# Core Components

## Overview

The `jobsearch/core` library provides foundational building blocks used across all features:

1. AI Integration (`core/ai.py`)
2. Database Management (`core/database.py`) 
3. Cloud Storage (`core/storage.py`)
4. Logging (`core/logging.py`)
5. Monitoring (`core/monitoring.py`)
6. Web Scraping (`core/web_scraper.py`)
7. Markdown Generation (`core/markdown.py`)
8. PDF Generation (`core/pdf.py`)
9. Template Management (`core/templates.py`)
10. Schema System (`core/schemas.py`)
11. Secrets Management (`core/secrets.py`)

## AI Integration

> **Related Documentation:**
> - [Core Components](ARCHITECTURE.md#core-components) - How features use AI capabilities
> - [MCP Integration](DEVELOPMENT.md#mcp-integration) - AI integration with MCP
> - [Template System](ARCHITECTURE.md#template-management) - Template-driven AI prompts

### AIEngine Class

```python
class AIEngine:
    """Core AI engine with monitoring and type safety."""
    
    def __init__(self, feature_name: str = 'default'):
        """Initialize the AI engine.
        
        Args:
            feature_name: Name of the feature using the engine
            
        Artifacts:
            - Sets up Logfire monitoring
            - Configures Gemini API
            - Initializes instrumentation
        """
        self.feature_name = feature_name
        self.instrumentation = monitoring_config.get_instrumentation_config(feature_name)
        
        # Configure monitoring with comprehensive tracking
        self.monitoring = LogfireMonitoring(
            project_id="jobsearch-ai",
            environment=os.getenv("ENVIRONMENT", "development"),
            service_name=feature_name,
            track_tokens=True,
            track_latency=True,
            track_retries=True,
            track_errors=True
        )
        
        # Configure Gemini
        configure_gemini()

    def get_agent(
        self,
        model: str = 'gemini-1.5-pro',
        output_type: Optional[Type[BaseModel]] = None
    ) -> Agent:
        """Get a monitored AI agent.
        
        Args:
            model: The model to use (default: gemini-1.5-pro)
            output_type: Expected Pydantic model for output validation
            
        Returns:
            Configured Agent instance with monitoring
        """
        return Agent(
            model=model,
            output_type=output_type,
            monitoring=self.monitoring,
            instrumentation=self.instrumentation
        )

    def get_prompt(
        self,
        template: str,
        example: Optional[Union[Dict, BaseModel]] = None
    ) -> Prompt:
        """Get a monitored prompt.
        
        Args:
            template: Prompt template
            example: Optional example data
            
        Returns:
            Configured Prompt instance with monitoring
        """
        return Prompt(
            template=template,
            example=example,
            monitoring=self.monitoring,
            instrumentation=self.instrumentation
        )

    async def generate(
        self,
        prompt: str,
        output_type: Type[BaseModel],
        example: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> Optional[BaseModel]:
        """Generate structured content with monitoring and validation.
        
        Args:
            prompt: The prompt to use
            output_type: Expected Pydantic model for output
            example: Optional example data to guide generation
            max_retries: Maximum retry attempts
            
        Returns:
            Validated content as Pydantic model or None on failure
            
        Artifacts:
            - Validates output against schema
            - Tracks token usage
            - Monitors latency
            - Handles retries
            - Logs errors
        """
        agent = self.get_agent(output_type=output_type)
        
        for attempt in range(max_retries):
            try:
                self.monitoring.increment('generate')
                result = await agent.generate(
                    prompt=prompt,
                    example=example,
                    generation_config=monitoring_config.get_generation_config(self.feature_name)
                )
                self.monitoring.track_success('generate')
                return result
                
            except ValidationError as e:
                self.monitoring.track_error('generate_validation', str(e))
                logger.error(f"Validation error on attempt {attempt + 1}: {str(e)}")
                
            except Exception as e:
                self.monitoring.track_error('generate', str(e))
                logger.error(f"Generation error on attempt {attempt + 1}: {str(e)}")
                
            if attempt == max_retries - 1:
                return None

    async def generate_text(
        self,
        prompt: str,
        max_length: Optional[int] = None,
        max_retries: int = 3
    ) -> Optional[str]:
        """Generate free-form text with monitoring.
        
        Args:
            prompt: The prompt to use
            max_length: Optional maximum length
            max_retries: Maximum retry attempts
            
        Returns:
            Generated text or None on failure
        
        Artifacts:
            - Tracks token usage
            - Monitors latency
            - Handles retries
            - Logs errors
        """
        agent = self.get_agent()
        
        for attempt in range(max_retries):
            try:
                self.monitoring.increment('generate_text')
                result = await agent.generate_text(
                    prompt=prompt,
                    max_length=max_length,
                    generation_config=monitoring_config.get_generation_config(self.feature_name)
                )
                self.monitoring.track_success('generate_text')
                return result
                
            except Exception as e:
                self.monitoring.track_error('generate_text', str(e))
                logger.error(
                    f"Text generation error in {self.feature_name} "
                    f"(attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
                
            if attempt == max_retries - 1:
                return None
```

### StructuredPrompt Class

```python
class StructuredPrompt:
    """Structured output generation from language models.
    
    This class provides template-based prompt generation with:
    - Type-safe output validation
    - Template inheritance
    - Context management
    - Error handling
    - Monitoring integration
    """
    
    def __init__(
        self,
        prompt_template: str,
        output_schema: Type[BaseModel],
        example: Optional[Dict[str, Any]] = None
    ):
        """Initialize structured prompt.
        
        Args:
            prompt_template: Jinja2 template for the prompt
            output_schema: Pydantic model for output validation
            example: Optional example output for few-shot learning
            
        Artifacts:
            - Sets up Jinja2 environment
            - Validates template syntax
            - Initializes monitoring
        """
        # Set up template engine with inheritance support
        self.env = Environment(
            loader=PackageLoader('jobsearch.core', 'templates'),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Load and validate template
        try:
            self.template = self.env.from_string(prompt_template)
        except TemplateError as e:
            logger.error(f"Template error: {str(e)}")
            raise
            
        self.output_schema = output_schema
        self.example = example
        
    def render(self, **kwargs) -> str:
        """Render prompt template with context.
        
        Args:
            **kwargs: Template variables
            
        Returns:
            Rendered prompt string
            
        Artifacts:
            - Validates required variables
            - Logs rendering errors
            - Updates monitoring metrics
        """
        try:
            monitoring.increment('prompt_render')
            result = self.template.render(**kwargs)
            monitoring.track_success('prompt_render')
            return result
        except Exception as e:
            monitoring.track_error('prompt_render', str(e))
            logger.error(f"Error rendering prompt: {str(e)}")
            raise
            
    async def execute(
        self,
        ai_engine: AIEngine,
        retry_different_examples: bool = True,
        **kwargs
    ) -> BaseModel:
        """Execute prompt and return structured output.
        
        Args:
            ai_engine: AIEngine instance to use
            retry_different_examples: Whether to try different examples on failure
            **kwargs: Template variables
            
        Returns:
            Validated output as Pydantic model
            
        Artifacts:
            - Validates output against schema
            - Handles retries with different examples
            - Logs execution metrics
            - Updates monitoring
        """
        try:
            monitoring.increment('prompt_execute')
            
            # Render prompt
            prompt = self.render(**kwargs)
            
            # Generate with current example
            result = await ai_engine.generate(
                prompt=prompt,
                output_type=self.output_schema,
                example=self.example
            )
            
            if result or not retry_different_examples:
                monitoring.track_success('prompt_execute')
                return result
                
            # Try with different examples
            for example in self._get_alternative_examples():
                result = await ai_engine.generate(
                    prompt=prompt,
                    output_type=self.output_schema,
                    example=example
                )
                if result:
                    monitoring.track_success('prompt_execute')
                    return result
                    
            monitoring.track_failure('prompt_execute')
            raise ValueError("Failed to generate valid output")
            
        except Exception as e:
            monitoring.track_error('prompt_execute', str(e))
            logger.error(f"Error executing prompt: {str(e)}")
            raise
            
    def _get_alternative_examples(self) -> List[Dict[str, Any]]:
        """Get alternative examples for retries."""
        return [
            example for example in self.env.globals.get('examples', [])
            if example != self.example
        ]
```

## Database Management

### Models

```python
class Base(DeclarativeBase):
    """Base class for all database models."""
    pass

class Experience(Base):
    """Professional experience model."""
    __tablename__ = "experiences"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str]
    title: Mapped[str]
    start_date: Mapped[str]
    end_date: Mapped[Optional[str]]
    description: Mapped[str]
    skills: Mapped[List["Skill"]] = relationship()

class JobCache(Base):
    """Cached job listing model."""
    __tablename__ = "job_cache"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    company: Mapped[str]
    description: Mapped[str]
    first_seen_date: Mapped[str]
    last_seen_date: Mapped[str]
```

### Session Management

```python
@contextmanager
def get_session() -> Session:
    """Get a managed database session with GCS sync and locking.
    
    This is the preferred way to get database sessions. It handles:
    - Database locking to prevent concurrent access
    - GCS sync before session start
    - GCS upload after successful commit
    - Proper cleanup and lock release
    - Monitoring and error tracking
    
    Example:
        with get_session() as session:
            job = session.query(JobCache).filter_by(url=url).first()
            if not job:
                job = JobCache(url=url, ...)
                session.add(job)
            # Auto-commits on success, rolls back on error
    
    Raises:
        Exception: If database lock cannot be acquired
        SQLAlchemyError: For database-related errors
    
    Artifacts:
        - Acquires database lock
        - Downloads latest from GCS
        - Uploads to GCS after commit
        - Updates monitoring metrics
        - Logs operations and errors
    """
    try:
        monitoring.increment('get_session')
        if not storage.acquire_lock():
            monitoring.track_failure('get_session')
            raise Exception("Could not acquire database lock after retries")
            
        storage.sync_db()  # Sync after acquiring lock
        session = SessionFactory()
        
        try:
            yield session
            session.commit()
            storage.upload_db()  # Upload after successful commit
            monitoring.track_success('get_session')
            
        except Exception as e:
            session.rollback()
            monitoring.track_error('get_session', str(e))
            raise
            
        finally:
            session.close()
            storage.release_lock()  # Always release lock
            
    except Exception as e:
        monitoring.track_error('get_session', str(e))
        logger.error(f"Error in database session: {str(e)}")
        raise
```

## Storage System

### Cloud Storage Manager

```python
class GCSManager:
    """Manages interaction with Google Cloud Storage."""
    
    def __init__(self):
        self.client = storage.Client()
        self.db_blob_name = 'career_data.db'
        self.local_db_path = Path(__file__).parent.parent / 'career_data.db'
        self.config_path = Path(__file__).parent.parent / 'config' / 'gcs.json'
        self.bucket_name = self._get_bucket_name()
        self.bucket = self.client.bucket(self.bucket_name)
        self.db_lock_blob_name = 'career_data.db.lock'
        self.lock_retry_attempts = 50
        self.lock_retry_delay = 0.5  # seconds
        
        # Create bucket if it doesn't exist
        self._ensure_bucket()
        
    def _get_bucket_name(self) -> str:
        """Get bucket name from config file."""
        try:
            monitoring.increment('config_read')
            if not self.config_path.exists():
                raise FileNotFoundError("GCS config file not found")
                
            with open(self.config_path) as f:
                config = json.load(f)
                
            if 'bucket_name' not in config:
                raise KeyError("bucket_name not found in GCS config")
                
            monitoring.track_success('config_read')
            return config['bucket_name']
        except Exception as e:
            monitoring.track_error('config_read', str(e))
            logger.error(f"Error reading GCS config: {str(e)}")
            raise
            
    def download_db(self) -> bool:
        """Download the database file from GCS."""
        try:
            monitoring.increment('db_download')
            blob = self.bucket.blob(self.db_blob_name)
            
            if not blob.exists():
                logger.info("No existing database in GCS")
                if not self.local_db_path.exists():
                    self.local_db_path.touch()
                return False
                
            logger.info("Downloading database from GCS")
            self._ensure_local_dir(self.local_db_path)
            blob.download_to_filename(self.local_db_path)
            
            monitoring.track_success('db_download')
            return True
        except Exception as e:
            monitoring.track_error('db_download', str(e))
            logger.error(f"Error downloading database: {str(e)}")
            if not self.local_db_path.exists():
                self.local_db_path.touch()
            return False
```

### File Management

```python
class FileManager:
    """Manages local and cloud file operations."""
    
    def __init__(self, feature_name: str):
        self.feature_name = feature_name
        self.storage = GCSManager()
        self.logger = setup_logging(feature_name)
        
    async def save_file(
        self,
        filename: str,
        content: Union[str, bytes],
        cloud_sync: bool = True
    ):
        """Save file locally and optionally to cloud."""
        # Save locally
        local_path = f"data/{self.feature_name}/{filename}"
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        with open(local_path, 'wb') as f:
            if isinstance(content, str):
                content = content.encode()
            f.write(content)
            
        # Sync to cloud
        if cloud_sync:
            await self.storage.upload_file(
                f"{self.feature_name}/{filename}",
                content
            )
```

## Monitoring System

### MonitoringConfig Class

```python
class MonitoringConfig:
    """Singleton class to manage monitoring configuration."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize monitoring configuration."""
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.slack_token = os.getenv("SLACK_API_TOKEN")
        self.slack_channel = os.getenv("SLACK_ALERT_CHANNEL", "#job-search-alerts")
        
        # Initialize Logfire monitoring
        self.monitoring = LogfireMonitoring(
            project_id="jobsearch-ai",
            environment=self.environment,
            service_name="job-search"
        )
        
        # Configure monitoring for different components
        self._setup_monitoring()
    
    def _setup_monitoring(self):
        """Configure monitoring alerts for different components."""
        # Job Search monitoring
        self.monitoring.set_alert(
            name="job_search_error_rate",
            condition="error_rate > 0.05",
            window="5m",
            channels=["slack"],
            alert_message="High error rate in job search: {error_rate:.1%}"
        )
        
        # Token usage monitoring
        self.monitoring.set_alert(
            name="high_token_usage",
            condition="hourly_tokens > 1000000",
            window="60m",
            channels=["slack"],
            alert_message="High token usage: {hourly_tokens:,} tokens in the last hour"
        )
        
    def get_instrumentation_config(self, feature_name: str) -> dict:
        """Get instrumentation configuration for a feature.
        
        Args:
            feature_name: Name of the feature to configure
            
        Returns:
            Dictionary with instrumentation configuration
        """
        return {
            'track_tokens': True,
            'track_latency': True,
            'track_errors': True,
            'track_retries': True,
            'track_success_rate': True,
            'feature': feature_name
        }
        
    def get_generation_config(self, feature_name: str) -> dict:
        """Get generation configuration for a feature.
        
        Args:
            feature_name: Name of the feature to configure
            
        Returns:
            Dictionary with generation configuration
        """
        # Base configuration
        config = {
            'temperature': 0.7,
            'top_p': 0.95,
            'top_k': 40,
            'max_output_tokens': 1024
        }
        
        # Feature-specific overrides
        if feature_name == 'job_analysis':
            config.update({
                'temperature': 0.5,  # More deterministic for analysis
                'max_output_tokens': 2048  # Longer outputs for analysis
            })
        elif feature_name == 'resume_generator':
            config.update({
                'temperature': 0.3,  # Very deterministic for resumes
                'max_output_tokens': 4096  # Very long outputs for resumes
            })
            
        return config
```

### setup_monitoring Function

```python
def setup_monitoring(component_name: str) -> MonitoringClient:
    """Set up monitoring for a component.
    
    Args:
        component_name: Name of the component to monitor
        
    Returns:
        Configured monitoring client
        
    Artifacts:
        - Sets up metrics tracking
        - Configures logging integration
        - Initializes alert system
    """
    monitoring_client = MonitoringClient(
        project_id="jobsearch-ai",
        component=component_name,
        environment=os.getenv("ENVIRONMENT", "development")
    )
    
    # Configure metrics
    monitoring_client.register_counter('requests', 'Number of requests')
    monitoring_client.register_counter('errors', 'Number of errors')
    monitoring_client.register_gauge('latency', 'Request latency in ms')
    
    # Configure monitoring handlers
    monitoring_client.add_handler(
        LogHandler(
            logger=logging.getLogger(component_name),
            level=logging.INFO
        )
    )
    
    # Add Slack handler if configured
    slack_token = os.getenv("SLACK_API_TOKEN")
    if slack_token:
        monitoring_client.add_handler(
            SlackHandler(
                token=slack_token,
                channel=os.getenv("SLACK_ALERT_CHANNEL", "#job-search-alerts"),
                threshold=0.05  # Alert on 5% error rate
            )
        )
    
    return monitoring_client
```

### SlackMonitoring Class

```python
class SlackMonitoring:
    """Handles integration between Logfire and Slack."""
    
    def __init__(
        self,
        slack_token: str,
        default_channel: str = "#job-search-alerts",
        environment: str = "production"
    ):
        """Initialize Slack monitoring.
        
        Args:
            slack_token: Slack API token
            default_channel: Default channel for alerts
            environment: Environment name for alerts
        """
        self.client = WebClient(token=slack_token)
        self.default_channel = default_channel.lstrip('#')  # Remove # for consistency
        self.environment = environment
        
        # Initialize Logfire monitoring
        self.monitoring = LogfireMonitoring(
            project_id="jobsearch-ai",
            environment=environment,
            service_name="job-search"
        )
        
    def ensure_channel_exists(self, channel_name: str) -> str:
        """Ensure a channel exists, create it if it doesn't.
        
        Args:
            channel_name: Name of the channel to check
            
        Returns:
            Channel ID if successful, None otherwise
        """
        channel_name = channel_name.lstrip('#')
        
        try:
            # Try to find existing channel
            response = self.client.conversations_list(types="public_channel")
            for channel in response["channels"]:
                if channel["name"] == channel_name:
                    return channel["id"]
            
            # Channel not found, create it
            logger.info(f"Creating new Slack channel: #{channel_name}")
            response = self.client.conversations_create(
                name=channel_name,
                is_private=False
            )
            return response["channel"]["id"]
        except SlackApiError as e:
            if "name_taken" in str(e):
                logger.warning(f"Channel #{channel_name} exists but bot doesn't have access")
                return None
            elif "not_allowed_token_type" in str(e):
                logger.error("Bot token doesn't have permission to create channels. Need channels:manage scope")
                return None
            else:
                logger.error(f"Error managing Slack channel: {str(e)}")
                return None
    
    def setup_error_rate_alert(
        self,
        channel: Optional[str] = None,
        threshold: float = 0.05,  # 5% error rate
        window_minutes: int = 5
    ):
        """Configure alert for high error rates.
        
        Args:
            channel: Slack channel for alerts (defaults to default_channel)
            threshold: Error rate threshold (0-1)
            window_minutes: Time window for calculation
        """
        alert_config = SlackAlert(
            channel=channel or self.default_channel,
            threshold=threshold,
            window_minutes=window_minutes,
            message_template=(
                ":warning: *High Error Rate Alert*\n"
                "Environment: {environment}\n"
                "Error Rate: {error_rate:.1%}\n"
                "Time Window: {window} minutes\n"
                "Most Common Errors:\n{error_breakdown}"
            )
        )
        
        self.monitoring.set_alert(
            name="high_error_rate",
            condition=f"error_rate > {threshold}",
            window=f"{window_minutes}m",
            channels=["slack"],
            handler=lambda data: self._send_error_alert(data, alert_config)
        )
        
    def setup_cost_alert(
        self,
        channel: Optional[str] = None,
        daily_budget: float = 50.0,  # $50 per day
        window_minutes: int = 60
    ):
        """Configure alert for unusual cost spikes.
        
        Args:
            channel: Slack channel for alerts (defaults to default_channel)
            daily_budget: Daily budget in USD
            window_minutes: Time window for calculation
        """
        alert_config = SlackAlert(
            channel=channel or self.default_channel,
            threshold=daily_budget,
            window_minutes=window_minutes,
            message_template=(
                ":moneybag: *Cost Alert*\n"
                "Environment: {environment}\n"
                "Current Spend: ${current_spend:.2f}\n"
                "Budget: ${budget:.2f}\n"
                "Time Window: {window} minutes\n"
                "Cost Breakdown:\n{cost_breakdown}"
            )
        )
        
        self.monitoring.set_alert(
            name="high_cost",
            condition=f"current_spend > {daily_budget}",
            window=f"{window_minutes}m",
            channels=["slack"],
            handler=lambda data: self._send_cost_alert(data, alert_config)
        )
    
    def setup_performance_alert(
        self,
        channel: Optional[str] = None,
        latency_threshold: float = 5.0,  # 5 seconds
        window_minutes: int = 15
    ):
        """Configure alert for performance issues.
        
        Args:
            channel: Slack channel for alerts (defaults to default_channel)
            latency_threshold: Latency threshold in seconds
            window_minutes: Time window for calculation
        """
        alert_config = SlackAlert(
            channel=channel or self.default_channel,
            threshold=latency_threshold,
            window_minutes=window_minutes,
            message_template=(
                ":snail: *Performance Alert*\n"
                "Environment: {environment}\n"
                "Average Latency: {latency:.1f}s\n"
                "Threshold: {threshold:.1f}s\n"
                "Time Window: {window} minutes\n"
                "Endpoint Breakdown:\n{latency_breakdown}"
            )
        )
        
        self.monitoring.set_alert(
            name="high_latency",
            condition=f"avg_latency > {latency_threshold}",
            window=f"{window_minutes}m",
            channels=["slack"],
            handler=lambda data: self._send_performance_alert(data, alert_config)
        )
        
    def setup_token_usage_alert(
        self,
        channel: Optional[str] = None,
        token_threshold: int = 1000000,  # 1M tokens
        window_minutes: int = 60
    ):
        """Configure alert for high token usage.
        
        Args:
            channel: Slack channel for alerts (defaults to default_channel)
            token_threshold: Token usage threshold
            window_minutes: Time window for calculation
        """
        alert_config = SlackAlert(
            channel=channel or self.default_channel,
            threshold=float(token_threshold),
            window_minutes=window_minutes,
            message_template=(
                ":chart_with_upwards_trend: *Token Usage Alert*\n"
                "Environment: {environment}\n"
                "Token Usage: {tokens:,}\n"
                "Threshold: {threshold:,}\n"
                "Time Window: {window} minutes\n"
                "Usage Breakdown:\n{token_breakdown}"
            )
        )
        
        self.monitoring.set_alert(
            name="high_token_usage",
            condition=f"token_count > {token_threshold}",
            window=f"{window_minutes}m",
            channels=["slack"],
            handler=lambda data: self._send_token_alert(data, alert_config)
        )
    
    def _send_message(self, channel: str, message: str):
        """Send a message to Slack channel.
        
        Args:
            channel: Target channel
            message: Message content
        """
        try:
            # Ensure channel exists first
            channel = channel.lstrip('#')
            channel_id = self.ensure_channel_exists(channel)
            
            if not channel_id:
                logger.error(f"Cannot send message - channel #{channel} is not accessible")
                return
                
            self.client.chat_postMessage(
                channel=f"#{channel}",
                text=message,
                unfurl_links=False,
                unfurl_media=False
            )
        except SlackApiError as e:
            error_message = e.response['error']
            logger.error(f"Error sending message to Slack: {error_message}")
            
            if "not_in_channel" in error_message:
                try:
                    # Try to join the channel
                    self.client.conversations_join(channel=channel_id)
                    # Retry sending message
                    self.client.chat_postMessage(
                        channel=f"#{channel}",
                        text=message,
                        unfurl_links=False,
                        unfurl_media=False
                    )
                except SlackApiError as join_error:
                    logger.error(f"Could not join channel: {str(join_error)}")
```

## Feature Integration

### FeatureContext Class

```python
class FeatureContext(BaseModel):
    """Base context class for all features."""
    feature_name: str
    
    def __init__(self, feature_name: str):
        super().__init__(feature_name=feature_name)
        self.logger = setup_logging(feature_name)
        self.storage = GCSManager()
        self.monitoring = setup_monitoring(feature_name)
```

### Feature Implementation Pattern

Each feature should:
1. Use the core components as building blocks
2. Define its own context and output types
3. Implement consistent error handling and monitoring
4. Follow the dependency injection pattern

```python
def create_job_search_feature(feature_name: str = 'job_search'):
    """Create a job search feature instance.
    
    Args:
        feature_name: Name for the feature (for logging/monitoring)
        
    Returns:
        Feature implementation with core components
    """
    # Initialize core components
    logger = setup_logging(feature_name)
    storage = GCSManager()
    monitoring = setup_monitoring(feature_name)
    ai_engine = AIEngine(feature_name=feature_name)
    
    async def search_jobs(query: str, location: str = None):
        """Run job search implementation."""
        try:
            monitoring.increment('search_jobs')
            
            with get_session() as session:
                # Fetch context data
                experiences = session.query(Experience).all()
                
                # Use AI engine for search
                result = await ai_engine.generate(
                    prompt=f"Find jobs matching {query} in {location}",
                    output_type=JobSearchResults
                )
                
                # Handle database updates
                for job in result.jobs:
                    _save_job(session, job)
                    
            monitoring.track_success('search_jobs')
            return result
            
        except Exception as e:
            monitoring.track_error('search_jobs', str(e))
            logger.error(f"Job search error: {str(e)}")
            raise
    
    def _save_job(session, job_data):
        """Save job to database."""
        job = JobCache(
            url=job_data.url,
            title=job_data.title,
            company=job_data.company,
            description=job_data.description,
            first_seen_date=datetime.now().strftime("%Y-%m-%d"),
            last_seen_date=datetime.now().strftime("%Y-%m-%d")
        )
        session.add(job)
    
    # Return public API
    return {
        'search': search_jobs,
        'logger': logger,
        'storage': storage,
        'monitoring': monitoring
    }
```

## Markdown Generation

### MarkdownGenerator Class

```python
class MarkdownGenerator:
    """Generates and formats markdown content."""
    
    def format_strategy(self, strategy: DailyStrategy) -> str:
        """Format a job search strategy as markdown.
        
        Args:
            strategy: DailyStrategy object containing strategy details
            
        Returns:
            Formatted markdown string
            
        Artifacts:
            - Tracks formatting metrics
            - Logs formatting errors
        """
        try:
            monitoring.increment('strategy_format')
            
            md = [
                f"# Job Search Strategy - {datetime.now().strftime('%Y-%m-%d')}\n",
                "## Today's Focus\n",
                f"{strategy.daily_focus.description}\n",
                "### Key Metrics\n"
            ]
            
            for metric in strategy.daily_focus.metrics:
                md.append(f"- {metric}\n")
                
            md.extend([
                "\n## Target Companies\n",
                *[f"- {company}\n" for company in strategy.target_companies],
                "\n## Networking Targets\n"
            ])
            
            for target in strategy.networking_targets:
                md.extend([
                    f"### {target.name} - {target.title}\n",
                    f"Company: {target.company}\n",
                    f"Source: {target.source}\n",
                    f"Notes: {target.notes}\n\n"
                ])
                
            md.extend([
                "## Action Items\n",
                "| Priority | Task | Deadline | Metrics |\n",
                "|----------|------|----------|----------|\n"
            ])
            
            for item in strategy.action_items:
                metrics = ", ".join(item.metrics)
                md.append(f"| {item.priority} | {item.description} | {item.deadline} | {metrics} |\n")
                
            monitoring.track_success('strategy_format')
            return "".join(md)
            
        except Exception as e:
            monitoring.track_error('strategy_format', str(e))
            logger.error(f"Error formatting strategy: {str(e)}")
            return ""
            
    def format_profile(self, profile: ProfileData) -> str:
        """Format profile data as markdown.
        
        Args:
            profile: ProfileData object with user profile information
            
        Returns:
            Formatted markdown string
            
        Artifacts:
            - Tracks formatting metrics
            - Logs formatting errors
        """
        try:
            monitoring.increment('profile_format')
            
            md = [
                "# Professional Profile\n\n",
                "## Skills\n",
                ", ".join(profile.skills),
                "\n\n## Target Roles\n",
                *[f"- {role}\n" for role in profile.target_roles],
                "\n## Experience\n"
            ]
            
            for exp in profile.experiences:
                md.extend([
                    f"### {exp['title']} at {exp['company']}\n",
                    f"{exp['description']}\n",
                    "**Skills:** " + ", ".join(exp['skills']) + "\n\n"
                ])
                
            monitoring.track_success('profile_format')
            return "".join(md)
            
        except Exception as e:
            monitoring.track_error('profile_format', str(e))
            logger.error(f"Error formatting profile: {str(e)}")
            return ""
            
    def format_job_analysis(self, analysis: JobAnalysis) -> str:
        """Format job analysis as markdown.
        
        Args:
            analysis: JobAnalysis object with analysis results
            
        Returns:
            Formatted markdown string with job analysis
            
        Artifacts:
            - Tracks formatting metrics
            - Logs formatting errors
        """
        try:
            monitoring.increment('analysis_format')
            
            md = [
                f"# Job Analysis\n\n",
                f"Match Score: {analysis.match_score}%\n\n",
                "## Key Requirements\n",
                *[f"- {req}\n" for req in analysis.key_requirements],
                "\n## Culture Indicators\n",
                *[f"- {ind}\n" for ind in analysis.culture_indicators],
                f"\n## Career Growth: {analysis.career_growth_potential}\n",
                f"Experience Required: {analysis.total_years_experience} years\n",
                f"Location Type: {analysis.location_type}\n",
                f"Company Size: {analysis.company_size}\n",
                f"Company Stability: {analysis.company_stability}\n\n"
            ]
            
            if analysis.candidate_gaps:
                md.extend([
                    "## Areas for Development\n",
                    *[f"- {gap}\n" for gap in analysis.candidate_gaps]
                ])
                
            monitoring.track_success('analysis_format')
            return "".join(md)
            
        except Exception as e:
            monitoring.track_error('analysis_format', str(e))
            logger.error(f"Error formatting job analysis: {str(e)}")
            return ""
    
    def format_github_pages(self, summary: GithubPagesSummary) -> str:
        """Format content for GitHub Pages.
        
        Args:
            summary: GithubPagesSummary object with page content
            
        Returns:
            Formatted markdown for GitHub Pages
            
        Artifacts:
            - Tracks formatting metrics
            - Logs formatting errors
        """
        try:
            monitoring.increment('pages_format')
            
            md = [
                f"# {summary.headline}\n\n",
                *[f"{para}\n\n" for para in summary.summary],
                "## Key Points\n",
                *[f"- {point}\n" for point in summary.key_points],
                "\n## Target Roles\n",
                *[f"- {role}\n" for role in summary.target_roles]
            ]
            
            monitoring.track_success('pages_format')
            return "".join(md)
            
        except Exception as e:
            monitoring.track_error('pages_format', str(e))
            logger.error(f"Error formatting GitHub Pages: {str(e)}")
            return ""
```

## PDF Generation

### PDFGenerator Class

```python
class PDFGenerator:
    """Handles PDF generation from HTML templates and text content."""

    def __init__(self, template_dir: Optional[Union[str, Path]] = None):
        """Initialize PDF generator.
        
        Args:
            template_dir: Optional path to template directory. If not provided,
                        templates will be fetched from GCS.
        """
        self.template_dir = Path(template_dir) if template_dir else None
        self.templates_loaded = {}
    
    def get_template_content(self, template_name: str) -> Optional[str]:
        """Get template content from GCS or local directory.
        
        Args:
            template_name: Name of the template file
            
        Returns:
            Template content as string, or None if not found
            
        Artifacts:
            - Caches templates for improved performance
            - Falls back to GCS if local file not found
        """
        if template_name in self.templates_loaded:
            return self.templates_loaded[template_name]

        if self.template_dir:
            template_path = self.template_dir / template_name
            if template_path.exists():
                content = template_path.read_text()
                self.templates_loaded[template_name] = content
                return content
        
        # Try GCS
        try:
            gcs_path = f'templates/{template_name}'
            if storage.file_exists(gcs_path):
                content = storage.download_as_string(gcs_path)
                self.templates_loaded[template_name] = content
                return content
        except Exception as e:
            logger.error(f"Error fetching template {template_name} from GCS: {str(e)}")
        
        return None
    
    def generate_pdf(
        self, 
        template_name: str,
        context: Dict[str, Any],
        output_path: Union[str, Path],
        css_string: Optional[str] = None
    ) -> bool:
        """Generate a PDF from a template and context.
        
        Args:
            template_name: Name of the HTML template file
            context: Dictionary of context variables for the template
            output_path: Path where to save the generated PDF
            css_string: Optional CSS string to apply
            
        Returns:
            True if PDF generation was successful, False otherwise
            
        Artifacts:
            - Creates temporary files for processing
            - Uses Jinja2 for template rendering
            - Generates PDF with WeasyPrint
        """
        try:
            # Get template content
            template_content = self.get_template_content(template_name)
            if not template_content:
                logger.error(f"Template {template_name} not found")
                return False

            # Create temporary files for HTML generation
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                
                # Create temporary HTML file
                temp_html = temp_dir_path / 'temp.html'
                
                # Set up Jinja environment
                env = Environment(loader=FileSystemLoader(str(temp_dir_path)))
                template = env.from_string(template_content)
                
                # Render template with context
                rendered_html = template.render(**context)
                temp_html.write_text(rendered_html)
                
                # Set up CSS
                css = CSS(string=css_string if css_string else '@page { margin: 1cm; }')
                
                # Generate PDF
                html = HTML(filename=str(temp_html))
                html.write_pdf(output_path, stylesheets=[css])
                
                return True
                
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            return False
    
    def generate_resume_pdf(
        self, 
        content: Dict[str, Any],
        output_path: Union[str, Path],
        visual: bool = False
    ) -> bool:
        """Generate a PDF resume.
        
        Args:
            content: Resume content dictionary
            output_path: Path to save the PDF
            visual: Whether to use the visual template
            
        Returns:
            True if successful, False otherwise
        """
        template = 'resume_visual.html' if visual else 'resume.html'
        return self.generate_pdf(template, {'content': content}, output_path)
    
    def generate_cover_letter_pdf(
        self,
        content: Dict[str, Any],
        job_info: Dict[str, Any],
        output_path: Union[str, Path],
        full_name: str = ""
    ) -> bool:
        """Generate a PDF cover letter.
        
        Args:
            content: Cover letter content dictionary
            job_info: Job information dictionary
            output_path: Path to save the PDF
            full_name: Optional name for the signature
            
        Returns:
            True if successful, False otherwise
        """
        context = {
            'content': content,
            'job_info': job_info,
            'full_name': full_name
        }
        return self.generate_pdf('cover_letter.html', context, output_path)
    
    def generate_from_text(
        self,
        text: str,
        output_path: Union[str, Path],
        title: Optional[str] = None,
        css_string: Optional[str] = None
    ) -> bool:
        """Generate a PDF from plain text.
        
        Args:
            text: Text content to convert to PDF
            output_path: Path to save the PDF
            title: Optional title for the document
            css_string: Optional CSS styling
            
        Returns:
            True if successful, False otherwise
        """
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                {f'<title>{title}</title>' if title else ''}
            </head>
            <body>
                <pre>{text}</pre>
            </body>
            </html>
            """
            
            # Create temporary files
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as temp_html:
                temp_html_path = Path(temp_html.name)
                temp_html.write(html_content)
                
            # Generate PDF
            html = HTML(filename=str(temp_html_path))
            css = CSS(string=css_string if css_string else '@page { margin: 1cm; }')
            html.write_pdf(output_path, stylesheets=[css])
            
            # Cleanup
            temp_html_path.unlink()
            return True
            
        except Exception as e:
            logger.error(f"Error generating PDF from text: {str(e)}")
            return False
    
    @staticmethod
    def setup_environment() -> bool:
        """Verify that the PDF generation environment is properly set up.
        
        Returns:
            True if environment is ready for PDF generation
        """
        try:
            # Create a simple test PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=True) as test_pdf:
                HTML(string="<p>Test</p>").write_pdf(test_pdf.name)
            return True
        except Exception as e:
            logger.error(f"PDF environment check failed: {str(e)}")
            return False
```

## Schema System

### Core Schema Models

```python
class LocationType(str, Enum):
    """Location type for job listings."""
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"
    FLEXIBLE = "flexible"

class CompanySize(str, Enum):
    """Company size classification."""
    STARTUP = "startup"
    SMALL = "small"
    MIDSIZE = "midsize"
    LARGE = "large"
    ENTERPRISE = "enterprise"

class StabilityLevel(str, Enum):
    """Company stability level."""
    EARLY_STAGE = "early_stage"
    GROWING = "growing"
    STABLE = "stable"
    ESTABLISHED = "established"
    DECLINING = "declining"

class GrowthPotential(str, Enum):
    """Career growth potential."""
    LIMITED = "limited"
    MODERATE = "moderate"
    STRONG = "strong"
    EXCEPTIONAL = "exceptional"

class CompanyAnalysis(BaseModel):
    """Detailed analysis of a company from job posting and external data."""
    company_name: str
    company_size: CompanySize
    company_stability: StabilityLevel
    glassdoor_rating: Optional[float] = None
    employee_count: Optional[str] = None
    industry: str
    funding_stage: Optional[str] = None
    benefits: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)
    culture_summary: str
    growth_opportunities: str
    market_position: str
    notable_leadership: Optional[str] = None

class JobAnalysis(BaseModel):
    """Complete analysis of a job posting."""
    match_score: int
    key_requirements: List[str]
    culture_indicators: List[str]
    career_growth_potential: GrowthPotential
    total_years_experience: int
    candidate_gaps: List[str] = Field(default_factory=list)
    location_type: LocationType
    company_analysis: CompanyAnalysis

class ResumeSection(BaseModel):
    """Section of a resume with title and content."""
    section_type: str
    title: Optional[str] = None
    content: str

class ResumeContent(BaseModel):
    """Complete structured resume content."""
    header: Dict[str, str]
    summary: str
    skills: List[str]
    experience: List[Dict[str, Any]]
    education: List[Dict[str, str]]
    sections: List[ResumeSection] = Field(default_factory=list)

class CoverLetterSection(BaseModel):
    """Section of a cover letter."""
    section_type: str
    content: str

class CoverLetterContent(BaseModel):
    """Complete structured cover letter content."""
    greeting: str
    introduction: str
    body: List[str]
    closing: str
    signature: Optional[str] = None

class ArticleSection(BaseModel):
    """Section of a technical article."""
    title: str
    content: str
    code_snippets: List[Dict[str, str]] = Field(default_factory=list)

class Article(BaseModel):
    """Complete structured article content."""
    title: str
    summary: str
    sections: List[ArticleSection]
    references: List[Dict[str, str]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

class FocusArea(BaseModel):
    """Daily job search focus area."""
    description: str
    metrics: List[str]
    activities: List[str]

class ActionItem(BaseModel):
    """Task action item for job search strategy."""
    description: str
    priority: str
    deadline: str
    metrics: List[str] = Field(default_factory=list)

class NetworkingTarget(BaseModel):
    """Person to network with for job search."""
    name: str
    title: str
    company: str
    source: str
    notes: str

class DailyStrategy(BaseModel):
    """Daily job search strategy."""
    daily_focus: FocusArea
    target_companies: List[str]
    networking_targets: List[NetworkingTarget] = Field(default_factory=list)
    action_items: List[ActionItem]

class StorageConfig(BaseModel):
    """Google Cloud Storage configuration."""
    GCS_BUCKET_NAME: str
    created_at: Optional[str] = None
    repository: Optional[str] = None

class ProfileData(BaseModel):
    """User profile data for job search."""
    name: str
    email: str
    phone: Optional[str] = None
    location: str
    summary: str
    skills: List[str]
    experiences: List[Dict[str, Any]]
    education: List[Dict[str, str]]
    target_roles: List[str]
    career_goals: Optional[str] = None

class GithubPagesSummary(BaseModel):
    """Summary content for GitHub Pages."""
    headline: str
    summary: List[str]
    key_points: List[str]
    target_roles: List[str]
    skills_highlight: Optional[List[str]] = None
    
class FeatureContext(BaseModel):
    """Base context class for all features."""
    feature_name: str
```

### Schema Usage Example

```python
from jobsearch.core.schemas import JobAnalysis, CompanyAnalysis, LocationType, CompanySize, StabilityLevel

async def analyze_job(job_url: str) -> JobAnalysis:
    """Analyze a job posting using core schemas."""
    # Get job data from URL
    job_data = await scraper.get_job_data(job_url)
    
    # Create company analysis
    company = CompanyAnalysis(
        company_name=job_data['company'],
        company_size=CompanySize.MIDSIZE,
        company_stability=StabilityLevel.STABLE,
        industry=job_data['industry'],
        culture_summary="Collaborative and innovative culture",
        growth_opportunities="Strong career advancement paths",
        market_position="Industry leader in their segment"
    )
    
    # Create job analysis with validated schema
    analysis = JobAnalysis(
        match_score=85,
        key_requirements=["Python", "Data Analysis", "Machine Learning"],
        culture_indicators=["Remote-first", "Flexible hours", "Continuing education"],
        career_growth_potential=GrowthPotential.STRONG,
        total_years_experience=3,
        candidate_gaps=["Cloud deployment", "Team leadership"],
        location_type=LocationType.REMOTE,
        company_analysis=company
    )
    
    return analysis
```
## Secrets Management

### SecretManager Class

```python
class SecretManager:
    """Manages secure access to sensitive credentials and API keys."""
    
    def __init__(self, secret_path: Optional[Union[str, Path]] = None):
        """Initialize secret manager.
        
        Args:
            secret_path: Optional path to local secrets file. If not provided,
                        will use default path in config directory.
        """
        if secret_path:
            self.secret_path = Path(secret_path)
        else:
            self.secret_path = Path(__file__).parent.parent / 'config' / 'secrets.json'
        
        # Cache for secrets to avoid repeated reads
        self._secret_cache = {}
        
        # Check if Secret Manager API should be used
        self.use_gcp = os.getenv("USE_GCP_SECRETS", "false").lower() in ["true", "1", "yes"]
        if self.use_gcp:
            try:
                from google.cloud import secretmanager
                self.client = secretmanager.SecretManagerServiceClient()
                self.project_id = os.getenv("GCP_PROJECT_ID")
                if not self.project_id:
                    logger.warning("GCP_PROJECT_ID not set, falling back to local secrets")
                    self.use_gcp = False
            except ImportError:
                logger.warning("google-cloud-secret-manager not installed, falling back to local secrets")
                self.use_gcp = False
    
    def get_secret(self, key: str) -> Optional[str]:
        """Get secret value by key.
        
        Args:
            key: Secret key to retrieve
            
        Returns:
            Secret value or None if not found
            
        Artifacts:
            - Caches secrets for performance
            - Falls back from GCP to local file
            - Logs access attempts (without values)
        """
        try:
            monitoring.increment('secret_access')
            
            # Check cache first
            if key in self._secret_cache:
                monitoring.track_success('secret_access')
                return self._secret_cache[key]
                
            # Try GCP Secret Manager first
            if self.use_gcp:
                secret = self._get_secret_from_gcp(key)
                if secret is not None:
                    self._secret_cache[key] = secret
                    monitoring.track_success('secret_access')
                    return secret
            
            # Fall back to local file
            if self.secret_path.exists():
                with open(self.secret_path) as f:
                    secrets = json.load(f)
                if key in secrets:
                    self._secret_cache[key] = secrets[key]
                    monitoring.track_success('secret_access')
                    return secrets[key]
            
            # Try environment variables
            env_key = key.upper()
            if env_key in os.environ:
                self._secret_cache[key] = os.environ[env_key]
                monitoring.track_success('secret_access')
                return os.environ[env_key]
                
            logger.warning(f"Secret {key} not found")
            monitoring.track_failure('secret_access')
            return None
            
        except Exception as e:
            logger.error(f"Error accessing secret {key}: {str(e)}")
            monitoring.track_error('secret_access', str(e))
            return None
    
    def _get_secret_from_gcp(self, key: str) -> Optional[str]:
        """Get secret from Google Cloud Secret Manager.
        
        Args:
            key: Secret key to retrieve
            
        Returns:
            Secret value or None if not found
        """
        try:
            name = f"projects/{self.project_id}/secrets/{key}/versions/latest"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.warning(f"Error accessing GCP secret {key}: {str(e)}")
            return None
    
    def set_secret(self, key: str, value: str) -> bool:
        """Set a secret in the local secrets file.
        
        Args:
            key: Secret key to set
            value: Secret value
            
        Returns:
            True if successful, False otherwise
            
        Note: This only updates local secrets, not GCP Secret Manager.
        """
        try:
            monitoring.increment('secret_set')
            
            # Read existing secrets
            secrets = {}
            if self.secret_path.exists():
                with open(self.secret_path) as f:
                    secrets = json.load(f)
            
            # Update secret
            secrets[key] = value
            
            # Ensure directory exists
            self.secret_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write secrets back
            with open(self.secret_path, 'w') as f:
                json.dump(secrets, f, indent=2)
                
            # Update cache
            self._secret_cache[key] = value
            
            monitoring.track_success('secret_set')
            return True
            
        except Exception as e:
            logger.error(f"Error setting secret {key}: {str(e)}")
            monitoring.track_error('secret_set', str(e))
            return False
            
    def clear_cache(self):
        """Clear the secret cache."""
        self._secret_cache.clear()
```

### secret_manager Instance

```python
# Global instance available for import
secret_manager = SecretManager()
```

### Example Usage

```python
from jobsearch.core.secrets import secret_manager

# Get API keys securely
api_key = secret_manager.get_secret("GEMINI_API_KEY")
slack_token = secret_manager.get_secret("SLACK_API_TOKEN")

# For local development, set a secret
if os.getenv("ENVIRONMENT") == "development":
    secret_manager.set_secret("LOCAL_TEST_KEY", "test-value-123")
```

## Logging

### setup_logging Function

```python
def setup_logging(logger_name: str) -> logging.Logger:
    """Set up logging configuration.
    
    Args:
        logger_name: Name of the logger to create
        
    Returns:
        Configured logger instance
        
    Artifacts:
        - Configures console and file logging
        - Sets appropriate log levels
        - Formats log messages
    """
    # Get or create logger
    logger = logging.getLogger(logger_name)
    
    # Only configure if it hasn't been configured already
    if not logger.handlers:
        # Set default level
        logger.setLevel(logging.INFO)
        
        # Create console handler
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Add formatter to handler
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)

    return logger
```

### Usage Examples

```python
from jobsearch.core.logging import setup_logging

# Simple usage
logger = setup_logging('my_component')
logger.info("Component initialized")
logger.error("Something went wrong", exc_info=True)

# With more context
component_logger = setup_logging('resume_generator')
component_logger.info(f"Generating resume for job: {job_title} at {company}")
try:
    # Do something
    pass
except Exception as e:
    component_logger.error(f"Error generating resume: {str(e)}", exc_info=True)
```

### Integration with Monitoring

The logging system integrates with the monitoring system to track errors:

```python
from jobsearch.core.logging import setup_logging
from jobsearch.core.monitoring import setup_monitoring

# Initialize both systems
logger = setup_logging('document_generator')
monitoring = setup_monitoring('document_generator')

try:
    monitoring.increment('generate_document')
    # Document generation logic
    monitoring.track_success('generate_document')
except Exception as e:
    logger.error(f"Document generation failed: {str(e)}", exc_info=True)
    monitoring.track_error('generate_document', str(e))
```
