# Claude Code Agent Definitions

This document contains the definitions and usage instructions for all available Claude Code subagents.

## Available Agents

### 1. Task Decomposer
**Purpose**: Break down high-level features, architectural designs, or complex requirements into manageable implementation tasks.

**When to use**:
- When you have a high-level feature request that needs to be broken into smaller tasks
- When a software architect has provided a system design that needs implementation planning
- When you need to identify which parts of the system need changes for a new feature

**Example usage**:
```
User: "We need to add a real-time notification system to our application"
Assistant: "I'll use the task-decomposer agent to break this down into manageable tasks and identify which parts of the system need changes"
```

**Key capabilities**:
- Creates structured task breakdowns with phases and dependencies
- Identifies affected systems and components
- Provides complexity estimates and risk assessments
- Outputs tasks suitable for the Code Analyst to analyze further

### 2. Code Analyst
**Purpose**: Analyze existing code and determine specific changes required to implement new features, fix bugs, or align with architectural designs.

**When to use**:
- When you have a bug report and need to know what specific code changes will fix it
- When you have an architectural design and need to determine how to implement it in the existing codebase
- When you need detailed code-level analysis and change specifications

**Example usage**:
```
User: "The system tester found that the API returns 500 errors when processing special characters. What changes are needed?"
Assistant: "I'll use the code-analyst agent to analyze the codebase and determine the specific code changes needed to fix this issue"
```

**Key capabilities**:
- Provides file-by-file change specifications with line numbers
- Identifies dependencies and ripple effects
- Maps high-level designs to specific code changes
- Creates detailed implementation roadmaps for the Implementation Engineer

### 3. Implementation Engineer
**Purpose**: Transform software designs, specifications, or architectural plans into working code implementations.

**When to use**:
- When you have a design document that needs to be implemented
- When you have API specifications that need to be coded
- When you have detailed change specifications from the Code Analyst

**Example usage**:
```
User: "I have this design for a JWT-based authentication system with refresh tokens. Can you implement it?"
Assistant: "I'll use the implementation-engineer agent to carefully implement this authentication system based on your design."
```

**Key capabilities**:
- Converts designs and specifications into production-ready code
- Implements with attention to security, performance, and maintainability
- Follows existing code patterns and conventions
- Structures code to be easily testable

### 4. System Tester
**Purpose**: Validate system or subsystem functionality by running tests, analyzing outputs, reviewing logs, and providing feedback on issues.

**When to use**:
- When you need to test a newly implemented feature
- When you're experiencing unexpected behavior and need debugging help
- When you want to verify that refactoring hasn't broken functionality
- When testing web applications with browser automation

**Example usage**:
```
User: "I've finished implementing the payment processing module. Can you test it?"
Assistant: "I'll use the system-tester agent to validate the payment processing module."
```

**Key capabilities**:
- Runs unit, integration, and end-to-end tests
- Uses Playwright MCP tools for browser-based testing
- Analyzes logs and identifies issues
- Reports problems without implementing fixes
- Provides detailed reproduction steps for bugs

### 5. Software Architect
**Purpose**: Provide high-level software design decisions including component architecture, technology selection, and communication patterns.

**When to use**:
- When designing a new system or microservices architecture
- When selecting technology stacks and frameworks
- When defining component boundaries and interfaces
- When establishing communication patterns between services

**Example usage**:
```
User: "I need to build a scalable e-commerce platform that can handle millions of users"
Assistant: "I'll use the software-architect agent to design the component architecture and technology stack for your e-commerce platform"
```

**Key capabilities**:
- Designs system architectures balancing technical excellence with practical constraints
- Recommends technology stacks with justifications
- Defines component boundaries and communication patterns
- Provides implementation roadmaps and architectural decision records

## Typical Workflow Patterns

### Feature Implementation
1. **Software Architect** (if new architecture needed) → designs system components
2. **Task Decomposer** → breaks down the feature into tasks
3. **Code Analyst** → analyzes code changes needed for each task
4. **Implementation Engineer** → implements the changes
5. **System Tester** → validates the implementation

### Bug Fix
1. **Code Analyst** → analyzes the bug and identifies fixes needed
2. **Implementation Engineer** → implements the fixes
3. **System Tester** → verifies the bug is fixed

### System Design
1. **Software Architect** → creates high-level architecture
2. **Task Decomposer** → breaks down into implementation phases
3. (Continue with implementation flow above)

## Important Notes

- Each agent has a specific role and should be used accordingly
- Agents work best when given clear, specific instructions
- The output from one agent often serves as input for the next
- System Tester only reports issues; it doesn't fix them
- Task Decomposer and Software Architect work at high level; Code Analyst works at code level
- Implementation Engineer focuses on faithful implementation of specifications

## Command Line Integration

To run lint and type checking after implementation:
- **JavaScript/TypeScript**: `npm run lint`, `npm run typecheck`
- **Python**: `ruff check`, `mypy`
- Always check project's package.json or configuration files for specific commands