from backend.lipvm import LipVM


def test_send_event_argument_is_flat():
    vm = LipVM("languages.statemachine")

    code = """statemachine SimpleFactory

            events
                start
                auto_primary
            
            initialState ResetState
            
            state ResetState
            
                auto_primary => IdleState
            
                tick: {
                    send_event(auto_primary)
                }
            
            end
            
            state IdleState
            end
            """

    vm.interpreter.interpret(code)
    vm.interpreter.tick()

    assert vm.interpreter.pending_events() == ["auto_primary"]
