# Contributing to i4g

> **Welcome!** Thank you for considering contributing to the **i4g (Information for Good)** project. This guide will help you get started.

---

## About the Project

**i4g** is a volunteer-driven, non-profit platform helping scam victims document and report fraud to law enforcement. We use AI (LangChain + Ollama) to classify scams, extract evidence, and generate police reports.

**Current Status**: Transitioning from prototype to production (Phase 1 MVP in progress)

---

## Who Can Contribute?

We welcome contributions from:

- **Software Engineers**: Python, FastAPI, React, cloud infrastructure
- **Graduate Students**: Computer science, data science, criminology (internship credits available)
- **Security Experts**: Penetration testing, compliance audits
- **UX/UI Designers**: Improving analyst dashboard and victim forms
- **Legal Advisors**: FERPA, GDPR, data privacy guidance
- **Scam Researchers**: Classification taxonomy, emerging fraud trends

**Time Commitment**: Flexible (as low as 2-5 hours/week)

---

## Getting Started

### 1. **Set Up Development Environment**

**Prerequisites**:
- Python 3.11+
- Docker Desktop
- Git
- Ollama (for local LLM testing)

**Clone the Repository**:
\`\`\`bash
git clone https://github.com/jsoung/i4g.git
cd i4g
\`\`\`

**Install Dependencies**:
\`\`\`bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install dev dependencies
pip install -e ".[dev]"
\`\`\`

**Run Tests**:
\`\`\`bash
pytest tests/ -v
\`\`\`

**Start Local API**:
\`\`\`bash
# In terminal 1: Start Ollama
ollama serve

# In terminal 2: Start FastAPI
python -m i4g.api.app
# API runs at http://localhost:8000
\`\`\`

**Start Dashboard**:
\`\`\`bash
cd src/i4g/dashboard
streamlit run app.py
# Dashboard runs at http://localhost:8501
\`\`\`

---

### 2. **Pick an Issue**

Browse our [GitHub Issues](https://github.com/jsoung/i4g/issues) for tasks labeled:

- \`good first issue\`: Beginner-friendly tasks (documentation, bug fixes)
- \`help wanted\`: Features we need assistance with
- \`bug\`: Something isn't working correctly
- \`enhancement\`: New feature or improvement

**Claim an Issue**:
1. Comment: "I'd like to work on this!"
2. Wait for maintainer approval (usually within 24 hours)
3. You'll be assigned the issue

---

### 3. **Create a Feature Branch**

\`\`\`bash
# Always branch from main
git checkout main
git pull origin main

# Create feature branch (use descriptive name)
git checkout -b feature/add-spanish-translation
# or
git checkout -b bugfix/fix-pdf-encoding
\`\`\`

**Branch Naming Convention**:
- \`feature/description\`: New functionality
- \`bugfix/description\`: Fixing a bug
- \`docs/description\`: Documentation updates
- \`test/description\`: Adding/improving tests
- \`refactor/description\`: Code cleanup

---

## Development Workflow

### Code Style

We follow **PEP 8** with some modifications:

\`\`\`python
# Good
def tokenize_pii(text: str) -> dict[str, str]:
    """Extract and tokenize PII from raw text.
    
    Args:
        text: Input string potentially containing PII
        
    Returns:
        Mapping of PII type to token ID
    """
    tokens = {}
    for pattern_name, regex in PII_PATTERNS.items():
        matches = regex.findall(text)
        for match in matches:
            token_id = generate_token()
            tokens[pattern_name] = token_id
    return tokens
\`\`\`

**Formatting Tools**:
\`\`\`bash
# Auto-format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/
\`\`\`

---

### Testing Requirements

**All code changes must include tests!**

**Test Coverage Targets**:
- Unit tests: 80% minimum
- Integration tests: Critical paths only
- E2E tests: Happy path + 1 error case

**Run Tests Before Committing**:
\`\`\`bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_pii_tokenizer.py

# Check coverage
pytest --cov=src/i4g --cov-report=html
open htmlcov/index.html
\`\`\`

---

### Commit Messages

Use **Conventional Commits** format:

\`\`\`
<type>(<scope>): <description>

[optional body]

[optional footer]
\`\`\`

**Examples**:
\`\`\`
feat(pii): add phone number tokenization

Added regex pattern to detect US/international phone numbers.
Includes tests for various formats.

Closes #42

---

fix(api): handle empty case description

Validation was failing when description field was null.
Now defaults to empty string.

Fixes #89
\`\`\`

**Types**:
- \`feat\`: New feature
- \`fix\`: Bug fix
- \`docs\`: Documentation changes
- \`test\`: Adding/updating tests
- \`refactor\`: Code restructuring (no behavior change)
- \`perf\`: Performance improvement
- \`chore\`: Tooling/dependencies

---

## Pull Request Process

### 1. **Push Your Branch**

\`\`\`bash
git add .
git commit -m "feat(analytics): add scam trend dashboard"
git push origin feature/add-scam-trends
\`\`\`

---

### 2. **Open Pull Request**

Go to [GitHub](https://github.com/jsoung/i4g/pulls) and click **"New Pull Request"**.

**PR Description Template**:
\`\`\`markdown
## Description
Brief summary of changes (2-3 sentences).

## Motivation
Why is this change needed? Link to issue if applicable.

## Changes Made
- Added X feature
- Refactored Y component
- Updated Z documentation

## Testing
- [ ] Unit tests pass (\`pytest tests/\`)
- [ ] Integration tests pass (if applicable)
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines (\`black\`, \`isort\`)
- [ ] Self-reviewed code
- [ ] Commented complex logic
- [ ] Updated documentation
- [ ] No breaking changes (or clearly documented)

Closes #[issue number]
\`\`\`

---

### 3. **Code Review**

**Review Timeline**:
- Initial feedback: Within 48 hours
- Follow-up: Within 24 hours after updates

**Approval Criteria**:
- At least 1 approval from maintainer (Jerry)
- All CI checks pass (tests, linting)
- No unresolved comments

---

## Communication Channels

### GitHub Issues
- **Use for**: Bug reports, feature requests, task tracking
- **Response time**: 24-48 hours

### GitHub Discussions
- **Use for**: Questions, ideas, general discussion
- **Categories**: Q&A, Ideas, Show & Tell

### Email
- **Project Lead**: jerry@i4g.org
- **Use for**: Security issues (use PGP if available), partnership inquiries

---

## Recognition & Credits

### Contributors Hall of Fame
All contributors are listed in [CONTRIBUTORS.md](./CONTRIBUTORS.md) with their contributions.

### Academic Credit
Graduate students can receive:
- **Internship Credit**: Coordinate with your advisor (we provide verification letters)
- **Research Publications**: Co-authorship on papers if you contribute significantly to research components

### Letters of Recommendation
Jerry provides reference letters for contributors who:
- Complete at least 3 meaningful PRs
- Participate for 3+ months
- Demonstrate reliability and quality work

---

## Graduate Student Onboarding

If you're a grad student joining through a university partnership:

### Week 1: Setup & Training
- [ ] Complete development environment setup
- [ ] Read [Data Compliance Guide](./COMPLIANCE.md)
- [ ] Sign FERPA Data Use Agreement (DUA)
- [ ] Complete PII handling quiz (80% passing score)
- [ ] Attend onboarding session (schedule via email)

### Week 2-3: First Contribution
- [ ] Pick a \`good first issue\`
- [ ] Submit first PR
- [ ] Attend code review session

### Week 4+: Regular Contributions
- [ ] Weekly check-ins (Mondays)
- [ ] Monthly progress report (for academic advisor)
- [ ] Bi-weekly pair programming (optional)

**Time Commitment**: 10 hours/week minimum

---

## Security & Confidentiality

### Sensitive Data Handling
- **NEVER commit**: Real PII, API keys, passwords
- **Use**: Git secrets scanner (automatically installed via pre-commit)
- **Report**: Any suspected data leak to security@i4g.org immediately

### Non-Disclosure
All contributors must sign a confidentiality agreement:
- Available at: [CONFIDENTIALITY_AGREEMENT.pdf](./CONFIDENTIALITY_AGREEMENT.pdf)
- Submit signed copy to: legal@i4g.org
- Renewal: Annually

---

## FAQ

**Q: I'm new to open source. Where should I start?**  
A: Check issues labeled \`good first issue\`. These are intentionally simple tasks like fixing typos, adding tests, or updating documentation.

**Q: How long does PR review take?**  
A: Initial review within 48 hours. If urgent, comment "@jsoung PTAL" (Please Take A Look).

**Q: Can I work on multiple issues at once?**  
A: Please limit to 1-2 active issues at a time to ensure quality and avoid blocking others.

**Q: I found a security vulnerability. What do I do?**  
A: **DO NOT open a public issue.** Email security@i4g.org with details. We'll respond within 24 hours.

**Q: Can I use i4g code in my research paper?**  
A: Yes! The project is MIT licensed. Please cite:  
\`\`\`
Soung, J. (2025). i4g: AI-Powered Scam Reporting Platform. 
GitHub repository: https://github.com/jsoung/i4g
\`\`\`

**Q: What if I can't finish an issue I claimed?**  
A: No problem! Just comment on the issue: "I'm unable to continue, feel free to reassign." Life happens!

---

## Code of Conduct

### Our Pledge
We are committed to providing a welcoming, inclusive, and harassment-free environment for all contributors.

### Expected Behavior
- Be respectful and constructive in feedback
- Assume good intent
- Focus on what's best for the project
- Acknowledge and learn from mistakes

### Unacceptable Behavior
- Harassment, discrimination, or offensive comments
- Personal attacks or trolling
- Publishing others' private information
- Any conduct that creates an unsafe environment

### Reporting
Email conduct@i4g.org with details. All reports are confidential.

**Enforcement**:
1st offense: Warning  
2nd offense: 2-week suspension  
3rd offense: Permanent ban

---

## License

By contributing to i4g, you agree that your contributions will be licensed under the **MIT License**.

---

## Thank You! 🙏

Every contribution—no matter how small—makes a difference in helping scam victims. We're grateful for your time and expertise.

**Questions?** Reach out to jerry@i4g.org or open a discussion on GitHub.

---

**Last Updated**: 2025-10-30  
**Maintainer**: Jerry Soung (@jsoung)
