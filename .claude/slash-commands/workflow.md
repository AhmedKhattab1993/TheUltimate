# Workflow Command

Execute predefined agent workflows for common development tasks.

## Usage

```
/workflow <workflow-type> <description>
```

## Available Workflows

### feature
Implements a new feature following the complete development cycle.

**Flow**: Software Architect (if needed) → Task Decomposer → Code Analyst → Implementation Engineer → System Tester

**Example**:
```
/workflow feature Add user authentication with JWT tokens
```

### bug
Fixes a bug through analysis, implementation, and testing.

**Flow**: Code Analyst → Implementation Engineer → System Tester

**Example**:
```
/workflow bug Fix API returning 500 errors when processing special characters
```

### design
Creates system architecture and implementation plan.

**Flow**: Software Architect → Task Decomposer

**Example**:
```
/workflow design Design microservices architecture for e-commerce platform
```

### test
Validates system functionality without implementation.

**Flow**: System Tester

**Example**:
```
/workflow test Verify payment processing module works correctly
```

### analyze
Analyzes code to determine changes needed without implementation.

**Flow**: Code Analyst

**Example**:
```
/workflow analyze Determine changes needed for adding caching layer
```

## Command Implementation

When you use `/workflow`, I will:

1. **Identify the workflow type** from your command
2. **Parse your description** to understand the task
3. **Execute the appropriate agent chain** automatically
4. **Coordinate handoffs** between agents
5. **Report results** from each stage

## Workflow Details

### Feature Implementation Workflow
1. **Software Architect** (optional): Designs system components if new architecture is needed
2. **Task Decomposer**: Breaks down the feature into manageable implementation tasks
3. **Code Analyst**: Analyzes each task to determine specific code changes
4. **Implementation Engineer**: Implements the code changes
5. **System Tester**: Validates the implementation

### Bug Fix Workflow
1. **Code Analyst**: Analyzes the bug and identifies root cause and fixes needed
2. **Implementation Engineer**: Implements the bug fixes
3. **System Tester**: Verifies the bug is resolved and no regressions

### Design Workflow
1. **Software Architect**: Creates high-level system design and technology choices
2. **Task Decomposer**: Breaks down architecture into implementation phases

### Test Workflow
1. **System Tester**: Runs tests and validates functionality

### Analyze Workflow
1. **Code Analyst**: Analyzes code and provides detailed change specifications

## Options

### --skip-architect
Skip the architect phase for feature workflow (when architecture is already defined).

**Example**:
```
/workflow feature --skip-architect Implement the already-designed caching layer
```

### --comprehensive
Run comprehensive analysis/testing (more thorough but slower).

**Example**:
```
/workflow test --comprehensive Full regression test of authentication system
```

### --context
Provide additional context for the workflow.

**Example**:
```
/workflow bug --context "Reported by customer, happens only with UTF-8 characters" Fix encoding issue in API
```

## Best Practices

1. **Be specific** in your descriptions - agents work better with clear requirements
2. **Include context** when relevant - error messages, requirements, constraints
3. **Use appropriate workflow** - don't use 'feature' for simple bugs
4. **Review agent outputs** - each agent's output feeds into the next

## Examples

### Complex Feature
```
/workflow feature Implement real-time notifications with WebSocket support, user preferences, and message history
```

### Critical Bug
```
/workflow bug --context "Production issue affecting 30% of users" Fix memory leak in data processing pipeline
```

### System Redesign
```
/workflow design Refactor monolithic application into microservices with event-driven communication
```

### Comprehensive Testing
```
/workflow test --comprehensive Validate new payment integration with all edge cases
```

### Pre-Implementation Analysis
```
/workflow analyze Determine impact of adding multi-tenancy to existing application
```

## Notes

- Workflows are stateless - each execution is independent
- Agents cannot communicate back after completion
- Results from each agent are passed to the next in the chain
- The workflow will stop if any agent encounters a blocking issue
- Use specific task descriptions for best results