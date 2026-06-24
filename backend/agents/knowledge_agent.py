#knowledge_agent.py
"""
Knowledge Gap Agent - Detects missing prerequisites before teaching

This agent ensures students learn concepts in the correct order by checking
if they have prerequisite knowledge before diving into advanced topics.

Example:
  - Student asks about "neural networks"
  - Agent checks: Does student know "matrix math"? "activation functions"?
  - If missing → First teach prerequisite
  - If known → Proceed to neural networks
"""

# Comprehensive prerequisite map for common AI/ML topics
# Note: Including both singular and plural forms for common topics
PREREQUISITES = {
    # Basic concepts
    "dataset": [],
    "datasets": [],
    "variables": ["dataset"],
    "variable": ["dataset"],
    "features": ["dataset", "variables"],
    "feature": ["dataset", "variables"],
    "labels": ["dataset", "variables"],
    "label": ["dataset", "variables"],
    
    # Statistics
    "mean": [],
    "standard deviation": ["mean"],
    "distribution": ["mean", "standard deviation"],
    "correlation": ["variables", "mean"],
    
    # Data manipulation
    "normalization": ["dataset", "features"],
    "scaling": ["dataset", "features"],
    "preprocessing": ["dataset", "normalization"],
    
    # Graphs and visualization
    "graph": ["dataset"],
    "graphs": ["dataset"],
    "histogram": ["graph", "dataset"],
    "scatter plot": ["graph", "variables"],
    "axis": ["graph"],
    "axes": ["graph"],
    
    # Linear algebra basics
    "matrix": [],
    "matrices": [],
    "vector": ["matrix"],
    "vectors": ["matrix"],
    "matrix multiplication": ["matrix", "vector"],
    "transpose": ["matrix"],
    
    # Linear relationship
    "line": ["graph"],
    "slope": ["line", "graph"],
    "intercept": ["line", "graph"],
    "linear relationship": ["slope", "intercept"],
    
    # Regression (progresses from basic to advanced)
    "linear regression": ["dataset", "variables", "line", "slope"],
    "regression": ["dataset", "variables"],
    "regression line": ["linear regression", "graph"],
    "least squares": ["linear regression", "matrix"],
    "polynomial regression": ["linear regression", "matrix"],
    "multiple regression": ["linear regression", "matrix"],
    
    # Supervised Learning
    "supervised learning": ["dataset", "labels"],
    "training data": ["dataset", "labels"],
    "test data": ["training data"],
    
    # Classification
    "classification": ["supervised learning", "labels"],
    "classify": ["supervised learning", "labels"],
    "classified label": ["classification"],
    "logistic regression": ["classification", "linear regression"],
    "decision tree": ["classification"],
    "random forest": ["decision tree"],
    
    # Neural networks (both singular and plural)
    "neuron": ["vector"],
    "neurons": ["vector"],
    "activation function": ["neuron"],
    "hidden layer": ["neuron", "activation function"],
    "hidden layers": ["neuron", "activation function"],
    "neural network": ["hidden layer", "matrix multiplication"],
    "neural networks": ["hidden layer", "matrix multiplication"],
    "backpropagation": ["neural network", "activation function"],
    "gradient descent": ["linear regression"],
    
    # Clustering
    "clustering": ["dataset", "features"],
    "cluster": ["dataset", "features"],
    "k-means": ["clustering", "mean"],
    "k means": ["clustering", "mean"],
    "distance metric": ["clustering"],
    
    # Ensemble methods
    "ensemble": ["classification"],
    "bagging": ["ensemble"],
    "boosting": ["ensemble"],
    
    # Dimensionality reduction
    "dimensionality reduction": ["dataset", "features"],
    "pca": ["dimensionality reduction", "matrix"],
    
    # Unsupervised Learning
    "unsupervised learning": ["dataset"],
    "anomaly detection": ["unsupervised learning"],
    
    # General ML
    "machine learning": ["dataset", "variables"],
    "model": ["machine learning"],
    "training": ["model", "training data"],
    "overfitting": ["training", "test data"],
    "cross validation": ["training data", "test data"],
    
    # Advanced topics
    "deep learning": ["neural network", "gradient descent"],
    "convolutional neural network": ["neural network", "matrix"],
    "convolutional neural networks": ["neural network", "matrix"],
    "cnn": ["neural network", "matrix"],
    "recurrent neural network": ["neural network", "sequence"],
    "recurrent neural networks": ["neural network", "sequence"],
    "rnn": ["neural network", "sequence"],
    "sequence": ["variables"],
    "time series": ["sequence", "dataset"],
    
    # Hyperparameters
    "hyperparameter": ["model", "training"],
    "hyperparameters": ["model", "training"],
    "learning rate": ["gradient descent", "hyperparameter"],
}

# Diagnostic questions for each concept
DIAGNOSTIC_QUESTIONS = {
    "dataset": "Do you know what a dataset is and why we need data to train models?",
    "variables": "Are you familiar with the concept of variables in data (like features in a spreadsheet)?",
    "features": "Do you understand what features are (the input variables we use to make predictions)?",
    "labels": "Do you know what labels are (the target values we want to predict)?",
    
    "mean": "Have you learned about calculating the average of a set of numbers?",
    "standard deviation": "Do you understand how standard deviation measures spread in data?",
    "distribution": "Are you familiar with how data can be distributed?",
    "correlation": "Do you know what correlation means between two variables?",
    
    "normalization": "Have you worked with normalizing or standardizing data to a similar scale?",
    "scaling": "Do you understand why we might scale features to similar ranges?",
    "preprocessing": "Are you familiar with data preprocessing steps?",
    
    "graph": "Are you comfortable reading and interpreting graphs or plots?",
    "histogram": "Have you worked with histograms to visualize data distribution?",
    "scatter plot": "Do you understand scatter plots and what they show about relationships?",
    "axis": "Are you familiar with X and Y axes on a graph?",
    
    "matrix": "Do you know what a matrix is (a grid of numbers)?",
    "vector": "Are you familiar with vectors (ordered lists of numbers)?",
    "matrix multiplication": "Have you learned how matrix multiplication works?",
    "transpose": "Do you know what it means to transpose a matrix?",
    
    "line": "Can you think about a straight line on a graph?",
    "slope": "Do you understand what slope means (how steep a line is)?",
    "intercept": "Do you know what the y-intercept is on a line?",
    "linear relationship": "Do you understand the concept of a linear relationship between two variables?",
    
    "linear regression": "Are you ready to learn about linear regression for predicting numbers?",
    "regression line": "Do you understand the concept of fitting a line to data?",
    "least squares": "Have you learned about finding the best-fit line using least squares?",
    "polynomial regression": "Are you familiar with fitting curves instead of straight lines?",
    "multiple regression": "Do you understand predicting using multiple input variables?",
    
    "supervised learning": "Do you know what supervised learning means (learning from labeled examples)?",
    "training data": "Have you heard about splitting data into training and testing sets?",
    "test data": "Do you understand why we test on separate data we didn't train on?",
    
    "classification": "Are you ready to learn classification (predicting categories)?",
    "classified label": "Do you understand the difference between predicting numbers vs categories?",
    "logistic regression": "Are you familiar with logistic regression for classification?",
    "decision tree": "Do you know what decision trees are?",
    "random forest": "Have you heard about combining multiple decision trees?",
    
    "neuron": "Do you understand the basic concept of artificial neurons?",
    "activation function": "Have you learned about activation functions in neural networks?",
    "hidden layer": "Do you know what hidden layers are in a neural network?",
    "neural network": "Are you ready to learn about neural networks?",
    "backpropagation": "Have you learned about backpropagation for training neural networks?",
    "gradient descent": "Do you understand gradient descent (how models learn)?",
    
    "clustering": "Are you ready to learn about clustering (grouping similar data)?",
    "k-means": "Do you know about the K-Means clustering algorithm?",
    "distance metric": "Do you understand how we measure distance between data points?",
    
    "ensemble": "Do you understand the idea of combining multiple models?",
    "bagging": "Have you heard about bagging in ensemble methods?",
    "boosting": "Do you know about boosting to improve model performance?",
    
    "dimensionality reduction": "Are you ready to learn about reducing the number of features?",
    "pca": "Have you heard about Principal Component Analysis?",
    
    "unsupervised learning": "Do you know about learning from unlabeled data?",
    "anomaly detection": "Are you interested in finding unusual patterns in data?",
    
    "machine learning": "Are you ready to start learning machine learning?",
    "model": "Do you understand what a model is?",
    "training": "Do you know what it means to train a model?",
    "overfitting": "Have you heard about overfitting and underfitting?",
    "cross validation": "Do you understand cross validation for better model evaluation?",
    
    "deep learning": "Are you ready for advanced deep learning topics?",
    "convolutional neural network": "Have you heard about CNNs for image processing?",
    "recurrent neural network": "Do you know about RNNs for sequence data?",
    "sequence": "Do you understand what sequential data is?",
    "time series": "Are you familiar with time series data?",
    
    "hyperparameter": "Do you understand what hyperparameters are?",
    "learning rate": "Have you heard about the learning rate in model training?",
}

# Teacher response templates for different prerequisites
PREREQUISITE_RESPONSES = {
    "dataset": """Before we dive into {current_concept}, let's make sure you understand datasets.

📘 Explanation
A dataset is a collection of information organized in a structured way. Think of it like a spreadsheet where:
- Each row represents one item (like one house)
- Each column represents a feature or property (like price, size, location)

📌 Example
A house dataset might look like:
| Size (sq ft) | Bedrooms | Price ($) |
|---|---|---|
| 1500 | 3 | 300,000 |
| 2000 | 4 | 400,000 |
| 1200 | 2 | 250,000 |

❓ Question
Can you think of a real-world dataset that interests you?""",

    "variables": """Before we dive into {current_concept}, let's make sure you understand variables in data.

📘 Explanation
Variables are the individual pieces of information we collect. In a dataset:
- Each column is a variable
- Variables can be numeric (like price or age) or categorical (like color or city)

📌 Example
For a house dataset, variables might be:
- Square footage (numeric)
- Number of bedrooms (numeric)
- Neighborhood (categorical)
- Has a pool? (yes/no)

❓ Question
If you were studying student performance, what variables would you collect?""",

    "labels": """Before we dive into {current_concept}, let's make sure you understand labels.

📘 Explanation
Labels are the target values we want to predict or classify. In supervised learning, labels are the answers we know and use to train our model.

📌 Example
For a house dataset used in supervised learning:
- The features are: size, bedrooms, location
- The label is: price (what we want to predict)

In a spam email detector:
- The features are: sender, subject, content
- The label is: spam or not spam (what we want to predict)

❓ Question
If you were predicting whether a student will pass an exam, what would be the label?""",

    "line": """Before we dive into {current_concept}, let's make sure you understand lines on graphs.

📘 Explanation
A line on a graph is a visual representation of a relationship between two variables. Each point on the line represents a sample in your data.

📌 Example
       |     •
       |    /
       |   / •
       |  /
       | •
       |_________

This line shows an increasing relationship between X and Y.

❓ Question
What do you think a flat horizontal line would mean?""",

    "slope": """Before we dive into {current_concept}, let's make sure you understand slope.

📘 Explanation
Slope measures how steep a line is. It tells you: "For every 1 unit I move right, how many units do I move up?"

📌 Example
If slope = 2:
- Every 1 sq ft increase → house price increases by $2

If slope = -0.5:
- Every 1 hour more → battery life decreases by 0.5%

❓ Question
What do you think a slope of 0 would represent?""",

    "matrix": """Before we dive into {current_concept}, let's make sure you understand matrices.

📘 Explanation
A matrix is a grid of numbers organized in rows and columns. It's just a way to organize data compactly.

📌 Example
This is a 2×3 matrix (2 rows, 3 columns):
[1  2  3]
[4  5  6]

Matrices are useful in machine learning for representing datasets and performing calculations.

❓ Question
If a dataset has 100 samples and 5 features, what size matrix would it be?""",

    "gradient descent": """Before we dive into {current_concept}, let's make sure you understand gradient descent.

📘 Explanation
Gradient descent is how machine learning models learn. Imagine you're on a hill blindfolded trying to reach the bottom. You can only feel the slope under your feet. You step in the downward direction. That's gradient descent — it's the process of gradually improving the model.

📌 Example
The model starts with bad predictions. With each step:
1. Calculate the error (how wrong we are)
2. Figure out which direction to improve
3. Take a small step in that direction
4. Repeat until we can't improve anymore

❓ Question
Why do you think we take small steps instead of big jumps?""",
}


def check_prerequisites(concept: str, student_message: str = "") -> list:
    """
    Check if student might be missing prerequisites for a concept.
    
    Args:
        concept: The concept being taught (e.g., "linear regression")
        student_message: The student's message (optional) to understand context
    
    Returns:
        list: List of missing prerequisite concepts (highest priority first)
    """
    
    missing = []
    concept_lower = concept.lower()
    student_lower = student_message.lower() if student_message else ""
    
    # Get prerequisites for this concept
    prereqs = PREREQUISITES.get(concept_lower, [])
    
    if not prereqs:
        return []  # No prerequisites for this concept
    
    # Check each prerequisite
    for prereq in prereqs:
        # Simple check: is the prerequisite mentioned in student's message?
        # A real implementation would use NLP or track student learning history
        if prereq not in student_lower:
            missing.append(prereq)
    
    return missing


def get_most_critical_gap(missing_gaps: list) -> str:
    """
    From list of missing prerequisites, return the most critical one to teach first.
    
    Args:
        missing_gaps: List of missing prerequisite concepts
    
    Returns:
        str: The most critical concept to teach
    """
    
    if not missing_gaps:
        return None
    
    # Priority: teach the most fundamental concept first
    # (the one with fewest or no prerequisites)
    priority_order = {
        "dataset": 0,
        "variables": 1,
        "features": 2,
        "matrix": 0,
        "graph": 1,
        "line": 2,
        "mean": 0,
    }
    
    # Sort by priority and return the highest priority (lowest number)
    sorted_gaps = sorted(
        missing_gaps,
        key=lambda x: priority_order.get(x.lower(), 999)
    )
    
    return sorted_gaps[0] if sorted_gaps else None


def generate_diagnostic_question(prerequisite: str) -> str:
    """
    Generate a diagnostic question to check if student knows a concept.
    
    Args:
        prerequisite: The concept to check (e.g., "dataset")
    
    Returns:
        str: A question to ask the student
    """
    
    return DIAGNOSTIC_QUESTIONS.get(
        prerequisite.lower(),
        f"Are you familiar with {prerequisite}?"
    )


def get_prerequisite_explanation(concept: str) -> str:
    """
    Get the explanation/teaching content for a missing prerequisite.
    
    Args:
        concept: The prerequisite concept to teach
    
    Returns:
        str: Formatted explanation with structure
    """
    
    template = PREREQUISITE_RESPONSES.get(
        concept.lower(),
        f"""Before we dive into the main topic, let me explain {concept}.

📘 Explanation
{concept} is an important foundational concept you'll need.

📌 Example
Think of {concept} like a building block for more advanced topics.

❓ Question
Does this make sense so far?"""
    )
    
    return template


def assess_knowledge_gap(
    concept: str,
    student_message: str,
    learning_history: list = None
) -> dict:
    """
    Comprehensive assessment of knowledge gaps.
    
    Args:
        concept: The concept student wants to learn
        student_message: What the student said
        learning_history: Previous messages in this session (optional)
    
    Returns:
        {
            "has_gap": bool,
            "missing_prerequisites": list,
            "critical_gap": str,
            "diagnostic_question": str,
            "ready_to_learn": bool
        }
    """
    
    # Check for missing prerequisites
    missing = check_prerequisites(concept, student_message)
    
    # Find the most critical gap
    critical = get_most_critical_gap(missing) if missing else None
    
    # Generate diagnostic question if there's a gap
    diagnostic = None
    if critical:
        diagnostic = generate_diagnostic_question(critical)
    
    return {
        "has_gap": len(missing) > 0,
        "missing_prerequisites": missing,
        "critical_gap": critical,
        "diagnostic_question": diagnostic,
        "ready_to_learn": critical is None,
        "gap_count": len(missing)
    }
