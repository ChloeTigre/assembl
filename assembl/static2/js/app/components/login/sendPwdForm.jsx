import React from 'react';
import { connect } from 'react-redux';
import { Translate, I18n } from 'react-redux-i18n';
import { form, FormGroup, FormControl, Button } from 'react-bootstrap';
import { Routes } from '../../routes';
import inputHandler from '../../utils/inputHandler';
import { requestPasswordChangeAction } from '../../actions/authenticationActions';

class SendPwdForm extends React.Component {
  constructor(props){
    super(props);
    this.state = {identifier: null};
    this.submitHandler = this.submitHandler.bind(this);
    this.handleInput = this.handleInput.bind(this);
    this.messageHandler = this.messageHandler.bind(this);
  }

  handleInput(e){
    inputHandler(this, e);
    const el = document.getElementById('sendPwdForm-error');
    if (el) { el.innerHTML = ''; }  // BUG: Only shows once; if fails beyond first time, no error shown!
  }

  messageHandler(){
    return (
      <div>
        {
          this.props.auth.passwordChangeRequest.success == null ? <span></span> : 
          <div id='sendPwdForm-error'><Translate value='login.passwordChangeRequestError' /></div> 
        }
      </div>
    )
  }

  submitHandler(e){
    e.preventDefault();
    this.props.sendRequest(this.state.identifier);
  }

  render() {
    return (
      <div className="login-view">
        <div className="box-title">
          <Translate value="login.forgotPwd" />
        </div>
        <div className="box">
          <form className="resendPwd" onSubmit={this.submitHandler}>
            <input type="hidden" name="referer" value="v2" />
            <FormGroup className="margin-m">
              <FormControl type="text" name="identifier" required
                           placeholder={I18n.t('login.username')} onChange={this.handleInput} />
            </FormGroup>
            <FormGroup>
              <Button type="submit" name="send_req_password" value={I18n.t('login.send')} className="button-submit button-dark">
                <Translate value="login.send" />
              </Button>
            </FormGroup>
          </form>
          <div className="error-message">
            {this.messageHandler()}
          </div>
        </div>
      </div>
    );
  }
}

const mapStateToProps = (state) => {
  return {
    auth: state.auth
  };
};

const mapDispatchToProps = (dispatch) => {
  return {
    sendRequest: (id) => dispatch(requestPasswordChangeAction(id))
  }
};

export default connect(mapStateToProps, mapDispatchToProps)(SendPwdForm);