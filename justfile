# K-IDS - Task Runner
# Run tasks with: just <task-name>

# Display all available commands
default:
    @just --list

ansible:
    cd ansible && ansible-playbook -i hosts playbook.yml

ansible-ping:
    cd ansible && ansible al -m ping

