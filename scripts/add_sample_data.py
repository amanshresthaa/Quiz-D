#!/usr/bin/env python3
"""
Script to add sample data for testing the quiz generation system.
"""

import asyncio
import sys
import os
import logging

# Add parent directory to path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion_pipeline import get_data_ingestion_pipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("add_sample_data")

# Sample content for testing
SAMPLE_CONTENT = {
    "python_basics": """
    Python Programming Language
    
    Python is a high-level, interpreted programming language known for its simplicity and readability.
    
    Key Features:
    - Easy to read and write syntax
    - Dynamic typing system
    - Extensive standard library
    - Object-oriented programming support
    - Cross-platform compatibility
    
    Data Types:
    Python has several built-in data types including:
    - Integers (int): Whole numbers like 1, 2, 3
    - Floats (float): Decimal numbers like 3.14, 2.7
    - Strings (str): Text data like "hello", "world"
    - Lists (list): Ordered collections like [1, 2, 3]
    - Dictionaries (dict): Key-value pairs like {"name": "John", "age": 30}
    - Booleans (bool): True or False values
    
    Control Structures:
    Python supports various control structures:
    - if/elif/else statements for conditional logic
    - for loops for iteration over sequences
    - while loops for repeated execution
    - try/except blocks for error handling
    
    Functions:
    Functions in Python are defined using the 'def' keyword.
    They can take parameters and return values.
    Example:
    def greet(name):
        return f"Hello, {name}!"
    """,
    
    "machine_learning": """
    Machine Learning Fundamentals
    
    Machine Learning (ML) is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed.
    
    Types of Machine Learning:
    
    1. Supervised Learning:
    - Uses labeled training data
    - Examples: Classification, Regression
    - Algorithms: Linear Regression, Decision Trees, Support Vector Machines
    
    2. Unsupervised Learning:
    - Works with unlabeled data
    - Examples: Clustering, Dimensionality Reduction
    - Algorithms: K-Means, PCA, Hierarchical Clustering
    
    3. Reinforcement Learning:
    - Learning through interaction with environment
    - Uses rewards and penalties
    - Examples: Game playing, Robotics
    
    Common Algorithms:
    - Linear Regression: Predicts continuous values
    - Decision Trees: Creates tree-like models of decisions
    - Random Forest: Ensemble of decision trees
    - Neural Networks: Inspired by biological neural networks
    - Support Vector Machines: Finds optimal decision boundaries
    
    Key Concepts:
    - Training Data: Data used to train the model
    - Test Data: Data used to evaluate model performance
    - Overfitting: Model performs well on training but poorly on new data
    - Cross-validation: Technique to assess model generalization
    - Feature Engineering: Process of selecting and transforming variables
    """,
    
    "data_science": """
    Data Science Overview
    
    Data Science is an interdisciplinary field that combines statistics, mathematics, programming, and domain expertise to extract insights from data.
    
    Data Science Process:
    
    1. Data Collection:
    - Gathering data from various sources
    - Web scraping, APIs, databases
    - Surveys and experiments
    
    2. Data Cleaning:
    - Handling missing values
    - Removing duplicates
    - Fixing inconsistent formats
    - Outlier detection and treatment
    
    3. Exploratory Data Analysis (EDA):
    - Understanding data distribution
    - Identifying patterns and relationships
    - Creating visualizations
    - Statistical summaries
    
    4. Feature Engineering:
    - Creating new variables from existing ones
    - Scaling and normalization
    - Encoding categorical variables
    - Dimensionality reduction
    
    5. Model Building:
    - Selecting appropriate algorithms
    - Training and validation
    - Hyperparameter tuning
    - Model evaluation
    
    6. Deployment:
    - Putting models into production
    - Monitoring performance
    - Updating models as needed
    
    Tools and Technologies:
    - Programming Languages: Python, R, SQL
    - Libraries: Pandas, NumPy, Scikit-learn, TensorFlow
    - Visualization: Matplotlib, Seaborn, Plotly
    - Big Data: Spark, Hadoop
    - Cloud Platforms: AWS, Azure, Google Cloud
    """,
    
    "artificial_intelligence": """
    Artificial Intelligence Introduction
    
    Artificial Intelligence (AI) is the simulation of human intelligence in machines that are programmed to think and learn like humans.
    
    History of AI:
    - 1950s: Alan Turing proposes the Turing Test
    - 1960s-1970s: Early AI programs and expert systems
    - 1980s: Machine learning emerges
    - 1990s: Statistical approaches gain popularity
    - 2000s: Big data and computational power increase
    - 2010s: Deep learning revolution
    
    Types of AI:
    
    1. Narrow AI (Weak AI):
    - Designed for specific tasks
    - Examples: Voice assistants, image recognition
    - Current state of most AI systems
    
    2. General AI (Strong AI):
    - Human-level intelligence across all domains
    - Currently theoretical
    - Goal of long-term AI research
    
    3. Superintelligence:
    - Beyond human intelligence
    - Speculative future possibility
    
    AI Applications:
    - Natural Language Processing: Understanding and generating human language
    - Computer Vision: Interpreting visual information
    - Robotics: Physical interaction with environment
    - Expert Systems: Knowledge-based decision making
    - Game Playing: Chess, Go, video games
    - Autonomous Vehicles: Self-driving cars
    - Healthcare: Medical diagnosis and treatment
    - Finance: Algorithmic trading and fraud detection
    
    Challenges:
    - Ethical considerations
    - Bias in algorithms
    - Job displacement
    - Privacy concerns
    - Safety and reliability
    """,
    
    "computer_science": """
    Computer Science Fundamentals
    
    Computer Science is the study of algorithms, computational systems, and the principles behind computing.
    
    Core Areas:
    
    1. Algorithms and Data Structures:
    - Algorithm analysis and complexity
    - Sorting and searching algorithms
    - Graph algorithms
    - Dynamic programming
    - Data structures: arrays, trees, graphs, hash tables
    
    2. Programming Languages:
    - Syntax and semantics
    - Compilers and interpreters
    - Object-oriented programming
    - Functional programming
    - Language design principles
    
    3. Computer Systems:
    - Computer architecture
    - Operating systems
    - Networking and distributed systems
    - Database systems
    - Computer security
    
    4. Software Engineering:
    - Software development lifecycle
    - Design patterns
    - Testing and debugging
    - Version control systems
    - Project management
    
    5. Theoretical Computer Science:
    - Computational complexity theory
    - Automata theory
    - Formal methods
    - Cryptography
    
    Programming Paradigms:
    - Imperative: Sequential execution of commands
    - Functional: Computation as evaluation of functions
    - Object-oriented: Organization around objects and classes
    - Logic: Declarative programming with logical relationships
    
    Important Concepts:
    - Big O Notation: Measuring algorithm efficiency
    - Recursion: Functions calling themselves
    - Abstraction: Hiding implementation details
    - Modularity: Breaking code into separate components
    - Debugging: Finding and fixing errors in code
    """
}

async def add_sample_data():
    """Add sample data to the system for testing."""
    logger.info("Starting to add sample data...")
    
    try:
        # Get the ingestion pipeline
        pipeline = get_data_ingestion_pipeline()
        
        # Process each piece of sample content
        for content_id, content_text in SAMPLE_CONTENT.items():
            logger.info(f"Processing content: {content_id}")
            
            # Add content to the pipeline
            result = await pipeline.ingest_content(
                title=content_id.replace("_", " ").title(),
                text=content_text,
                source="sample_data",
                metadata={
                    "source": "sample_data",
                    "topic": content_id.replace("_", " ").title(),
                    "created_by": "add_sample_data.py"
                }
            )
            
            if result and result.get("success", False):
                logger.info(f"Successfully processed {content_id}")
            else:
                logger.error(f"Failed to process {content_id}: {result}")
        
        # Get pipeline statistics
        stats = pipeline.get_pipeline_statistics()
        logger.info(f"Pipeline statistics: {stats}")
        
        logger.info("Sample data addition completed!")
        
    except Exception as e:
        logger.error(f"Error adding sample data: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(add_sample_data())
