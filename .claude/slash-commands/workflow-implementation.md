# Workflow Command Implementation Guide

This document provides the implementation logic for the `/workflow` slash command.

## Command Parser Logic

```typescript
interface WorkflowCommand {
  type: 'feature' | 'bug' | 'design' | 'test' | 'analyze'
  description: string
  options: {
    skipArchitect?: boolean
    comprehensive?: boolean
    context?: string
  }
}

function parseWorkflowCommand(input: string): WorkflowCommand {
  const parts = input.split(' ')
  const type = parts[0] as WorkflowCommand['type']
  
  // Extract options
  const options: WorkflowCommand['options'] = {}
  let descriptionParts: string[] = []
  
  for (let i = 1; i < parts.length; i++) {
    if (parts[i].startsWith('--')) {
      const option = parts[i].substring(2)
      if (option === 'skip-architect') {
        options.skipArchitect = true
      } else if (option === 'comprehensive') {
        options.comprehensive = true
      } else if (option === 'context' && parts[i + 1]) {
        // Find quoted context
        const contextStart = input.indexOf('"', input.indexOf('--context'))
        const contextEnd = input.indexOf('"', contextStart + 1)
        options.context = input.substring(contextStart + 1, contextEnd)
        i = parts.indexOf(parts.find(p => p.includes(contextEnd))!)
      }
    } else if (!options.context || i > parts.indexOf('--context') + 1) {
      descriptionParts.push(parts[i])
    }
  }
  
  return {
    type,
    description: descriptionParts.join(' '),
    options
  }
}
```

## Workflow Execution Templates

### Feature Workflow

```javascript
async function executeFeatureWorkflow(description: string, options: WorkflowCommand['options']) {
  const agents = []
  
  // Step 1: Software Architect (optional)
  if (!options.skipArchitect) {
    agents.push({
      type: 'software-architect',
      prompt: `Design the architecture for: ${description}
      
Focus on:
- Component structure and boundaries
- Technology stack recommendations
- Communication patterns between components
- Scalability and performance considerations
- Security architecture

${options.context ? `Additional context: ${options.context}` : ''}`
    })
  }
  
  // Step 2: Task Decomposer
  agents.push({
    type: 'task-decomposer',
    prompt: `Break down this feature into implementation tasks: ${description}

${!options.skipArchitect ? 'Use the architecture design from the previous step.' : ''}
${options.context ? `Additional context: ${options.context}` : ''}

Create a detailed task breakdown with:
- Clear implementation phases
- Dependencies between tasks
- Affected system components
- Complexity estimates`
  })
  
  // Step 3: Code Analyst (for each task)
  agents.push({
    type: 'code-analyst',
    prompt: `Analyze the codebase to determine specific changes needed for: ${description}

Use the task breakdown from the previous step.
${options.context ? `Additional context: ${options.context}` : ''}

For each task, provide:
- Exact files and functions to modify
- Specific code changes required
- Integration points
- Potential impacts and risks`
  })
  
  // Step 4: Implementation Engineer
  agents.push({
    type: 'implementation-engineer',
    prompt: `Implement the following feature: ${description}

Use the code analysis and specifications from the previous step.
${options.context ? `Additional context: ${options.context}` : ''}

Ensure:
- Follow existing code patterns and conventions
- Implement proper error handling
- Add necessary validation
- Structure code for testability`
  })
  
  // Step 5: System Tester
  agents.push({
    type: 'system-tester',
    prompt: `Test the implementation of: ${description}

${options.comprehensive ? 'Perform comprehensive testing including:' : 'Perform standard testing including:'}
- Functional testing of all new features
- Integration testing with existing components
- Edge case validation
- Performance impact assessment
${options.comprehensive ? '- Security testing\n- Load testing\n- Backward compatibility checks' : ''}

Report any issues found with clear reproduction steps.`
  })
  
  return agents
}
```

### Bug Workflow

```javascript
async function executeBugWorkflow(description: string, options: WorkflowCommand['options']) {
  return [
    {
      type: 'code-analyst',
      prompt: `Analyze and identify the root cause of this bug: ${description}

${options.context ? `Additional context: ${options.context}` : ''}

Determine:
- Root cause analysis
- All code locations that need fixes
- Impact assessment
- Similar issues that might exist elsewhere`
    },
    {
      type: 'implementation-engineer',
      prompt: `Fix the following bug: ${description}

Use the analysis from the previous step.
${options.context ? `Additional context: ${options.context}` : ''}

Ensure:
- Fix addresses the root cause, not just symptoms
- No regressions are introduced
- Proper error handling is in place
- Add safeguards to prevent recurrence`
    },
    {
      type: 'system-tester',
      prompt: `Verify the bug fix for: ${description}

${options.comprehensive ? 'Perform comprehensive testing:' : 'Perform focused testing:'}
- Confirm the bug is fixed
- Test edge cases around the fix
- Verify no regressions were introduced
${options.comprehensive ? '- Test related functionality\n- Performance impact check' : ''}

${options.context ? `Original issue context: ${options.context}` : ''}`
    }
  ]
}
```

### Design Workflow

```javascript
async function executeDesignWorkflow(description: string, options: WorkflowCommand['options']) {
  return [
    {
      type: 'software-architect',
      prompt: `Create a comprehensive system design for: ${description}

${options.context ? `Additional context: ${options.context}` : ''}

Include:
- High-level architecture overview
- Component breakdown and responsibilities
- Technology stack recommendations
- Data flow and storage design
- API/Interface specifications
- Security and scalability considerations
- Deployment architecture`
    },
    {
      type: 'task-decomposer',
      prompt: `Create an implementation plan for this architecture: ${description}

Use the system design from the previous step.
${options.context ? `Additional context: ${options.context}` : ''}

Break down into:
- Implementation phases
- Component dependencies
- Integration milestones
- Risk mitigation strategies
- Resource requirements`
    }
  ]
}
```

### Test Workflow

```javascript
async function executeTestWorkflow(description: string, options: WorkflowCommand['options']) {
  return [
    {
      type: 'system-tester',
      prompt: `${options.comprehensive ? 'Perform comprehensive testing' : 'Perform testing'} for: ${description}

${options.context ? `Additional context: ${options.context}` : ''}

Include:
- Functional validation
- Integration testing
- Error handling verification
${options.comprehensive ? `- Performance testing
- Security testing
- Load/stress testing
- Compatibility testing
- Regression testing` : ''}

Provide detailed test results and any issues found.`
    }
  ]
}
```

### Analyze Workflow

```javascript
async function executeAnalyzeWorkflow(description: string, options: WorkflowCommand['options']) {
  return [
    {
      type: 'code-analyst',
      prompt: `Perform ${options.comprehensive ? 'comprehensive' : 'focused'} analysis for: ${description}

${options.context ? `Additional context: ${options.context}` : ''}

Analyze:
- Current implementation details
- Required changes and impacts
- Technical feasibility
- Risk assessment
${options.comprehensive ? `- Performance implications
- Security considerations
- Scalability impacts
- Alternative approaches` : ''}

Provide detailed findings and recommendations.`
    }
  ]
}
```

## Main Execution Function

```javascript
async function executeWorkflow(command: string) {
  const parsed = parseWorkflowCommand(command)
  
  let agents
  switch (parsed.type) {
    case 'feature':
      agents = await executeFeatureWorkflow(parsed.description, parsed.options)
      break
    case 'bug':
      agents = await executeBugWorkflow(parsed.description, parsed.options)
      break
    case 'design':
      agents = await executeDesignWorkflow(parsed.description, parsed.options)
      break
    case 'test':
      agents = await executeTestWorkflow(parsed.description, parsed.options)
      break
    case 'analyze':
      agents = await executeAnalyzeWorkflow(parsed.description, parsed.options)
      break
    default:
      throw new Error(`Unknown workflow type: ${parsed.type}`)
  }
  
  // Execute agents in sequence
  for (const agent of agents) {
    await invokeAgent(agent.type, agent.prompt)
  }
}
```

## Usage in Claude

When the user types `/workflow`, Claude should:

1. Parse the command using the logic above
2. Determine the appropriate workflow
3. Use the Task tool to invoke each agent in sequence
4. Pass results from one agent to the next
5. Summarize the overall results for the user

## Example Implementation

```
User: /workflow feature Add user authentication with JWT tokens

Claude: I'll execute the feature implementation workflow for adding JWT authentication.

[Invokes Task tool with software-architect agent]
[Receives architecture design]
[Invokes Task tool with task-decomposer agent using architecture]
[Receives task breakdown]
[Invokes Task tool with code-analyst agent for each major task]
[Receives code analysis]
[Invokes Task tool with implementation-engineer agent]
[Receives implementation confirmation]
[Invokes Task tool with system-tester agent]
[Receives test results]

Claude: Feature implementation completed successfully:
- Architecture: Designed JWT-based auth system with refresh tokens
- Tasks: Broken down into 5 implementation phases
- Analysis: Identified changes needed in 12 files
- Implementation: All changes implemented successfully
- Testing: All tests passing, no issues found
```